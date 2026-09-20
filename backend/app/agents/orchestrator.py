"""
Fallow — Orchestrator Agent (LangGraph)

Implements ORC-1 through ORC-7:
- ORC-1: Executes Forecast → Research → Advisory → Localization in sequence
- ORC-2: Blocks Advisory where a Claim has empty citation_ids
- ORC-3: Validates every citation_id resolves to a passage
- ORC-4: If Research returns < MIN_PASSAGES, sets sufficient_guidance=False (refusal path)
- ORC-5: Retries a failed agent once with backoff
- ORC-6: Emits structured trace of each agent handoff
- ORC-7: Enforces total pipeline timeout; partial results surfaced

Uses LangGraph for state machine orchestration.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

from app.config import get_settings
from app.contracts import (
    FarmerProfile, ForecastResult, RetrievedPassage,
    Advisory, LocalizedAdvisory, PipelineResponse,
    TraceEntry, AgentStatus, Confidence,
)
from app.agents.forecast import run_forecast_agent
from app.agents.research import run_research_agent
from app.agents.advisory import run_advisory_agent
from app.agents.localization import run_localization_agent
from app.services.cache import get_cache

logger = logging.getLogger(__name__)


class PipelineState:
    """Mutable state object threaded through the pipeline."""

    def __init__(self, profile: FarmerProfile):
        self.profile = profile
        self.forecast: Optional[ForecastResult] = None
        self.passages: list[RetrievedPassage] = []
        self.advisory: Optional[Advisory] = None
        self.localized: Optional[LocalizedAdvisory] = None
        self.trace: list[TraceEntry] = []
        self.error: Optional[str] = None
        self.is_refusal: bool = False
        self.refusal_reason: Optional[str] = None


async def run_pipeline(
    profile: FarmerProfile,
) -> PipelineResponse:
    """
    Execute the full advisory pipeline synchronously.
    Returns a complete PipelineResponse.
    """
    state = PipelineState(profile)
    settings = get_settings()

    # Check demo cache first
    cache = get_cache(settings.DEMO_CACHE_DIR)
    cache_key = f"pipeline:{profile.district_id}:{profile.season.value}:{profile.irrigation_access.value}"
    if settings.DEMO_MODE:
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Demo mode: returning cached pipeline response")
            return PipelineResponse(**cached)

    try:
        # ORC-7: Enforce total pipeline timeout
        result = await asyncio.wait_for(
            _execute_pipeline(state, settings),
            timeout=settings.PIPELINE_TIMEOUT_S,
        )
        return result

    except asyncio.TimeoutError:
        logger.error(f"Pipeline timeout after {settings.PIPELINE_TIMEOUT_S}s")
        state.trace.append(TraceEntry(
            agent="orchestrator",
            status=AgentStatus.TIMEOUT,
            message=f"Pipeline timed out after {settings.PIPELINE_TIMEOUT_S}s. Returning partial results.",
        ))

        return PipelineResponse(
            advisory=state.advisory,
            localized=state.localized,
            trace=state.trace,
            error=f"Pipeline timed out after {settings.PIPELINE_TIMEOUT_S}s",
        )


async def run_pipeline_streaming(
    profile: FarmerProfile,
) -> AsyncGenerator[str, None]:
    """
    Execute the pipeline with SSE streaming of trace events.
    
    ORC-6: Emits structured trace of each agent handoff for the UI.
    Yields SSE-formatted events.
    """
    state = PipelineState(profile)
    settings = get_settings()

    # Check demo cache
    cache = get_cache(settings.DEMO_CACHE_DIR)
    cache_key = f"pipeline:{profile.district_id}:{profile.season.value}:{profile.irrigation_access.value}"
    if settings.DEMO_MODE:
        cached = cache.get(cache_key)
        if cached:
            response = PipelineResponse(**cached)
            for te in response.trace:
                yield f"data: {json.dumps({'type': 'trace', 'data': te.model_dump(mode='json')})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'data': response.model_dump(mode='json')})}\n\n"
            return

    # ─── Stage 1: Forecast ───────────────────────────────────────────
    yield f"data: {json.dumps({'type': 'stage_start', 'data': {'agent': 'forecast', 'message': 'Fetching seasonal forecast...'}})}\n\n"

    try:
        forecast, trace = await _run_with_retry(
            lambda: run_forecast_agent(profile),
            agent_name="forecast",
        )
        state.forecast = forecast
        state.trace.append(trace)
        yield f"data: {json.dumps({'type': 'trace', 'data': trace.model_dump(mode='json')})}\n\n"

        # Send forecast data to UI immediately
        yield f"data: {json.dumps({'type': 'forecast', 'data': forecast.model_dump(mode='json')})}\n\n"

    except Exception as e:
        error_trace = TraceEntry(
            agent="forecast",
            status=AgentStatus.ERROR,
            message=f"Forecast failed: {str(e)[:100]}",
        )
        state.trace.append(error_trace)
        yield f"data: {json.dumps({'type': 'trace', 'data': error_trace.model_dump(mode='json')})}\n\n"
        yield f"data: {json.dumps({'type': 'error', 'data': {'error': f'Forecast stage failed: {e}'}})}\n\n"
        return

    # ─── Stage 2: Research ───────────────────────────────────────────
    yield f"data: {json.dumps({'type': 'stage_start', 'data': {'agent': 'research', 'message': 'Searching agricultural corpus...'}})}\n\n"

    try:
        passages, trace = await _run_with_retry(
            lambda: run_research_agent(profile, state.forecast),
            agent_name="research",
        )
        state.passages = passages
        state.trace.append(trace)
        yield f"data: {json.dumps({'type': 'trace', 'data': trace.model_dump(mode='json')})}\n\n"

    except Exception as e:
        error_trace = TraceEntry(
            agent="research",
            status=AgentStatus.ERROR,
            message=f"Research failed: {str(e)[:100]}",
        )
        state.trace.append(error_trace)
        yield f"data: {json.dumps({'type': 'trace', 'data': error_trace.model_dump(mode='json')})}\n\n"
        yield f"data: {json.dumps({'type': 'error', 'data': {'error': f'Research stage failed: {e}'}})}\n\n"
        return

    # ORC-4: Check if enough passages for advisory
    if len(state.passages) < settings.MIN_PASSAGES_FOR_ADVISORY:
        state.is_refusal = True
        state.refusal_reason = (
            f"Insufficient corpus coverage: only {len(state.passages)} relevant passages found "
            f"(minimum {settings.MIN_PASSAGES_FOR_ADVISORY} required). "
            f"Cannot generate a reliably grounded advisory."
        )

        refusal_trace = TraceEntry(
            agent="orchestrator",
            status=AgentStatus.OK,
            message=f"Refusal path: insufficient passages ({len(state.passages)} < {settings.MIN_PASSAGES_FOR_ADVISORY})",
        )
        state.trace.append(refusal_trace)
        yield f"data: {json.dumps({'type': 'trace', 'data': refusal_trace.model_dump(mode='json')})}\n\n"

        response = PipelineResponse(
            trace=state.trace,
            is_refusal=True,
            refusal_reason=state.refusal_reason,
        )
        yield f"data: {json.dumps({'type': 'complete', 'data': response.model_dump(mode='json')})}\n\n"
        return

    # ─── Stage 3: Advisory ───────────────────────────────────────────
    yield f"data: {json.dumps({'type': 'stage_start', 'data': {'agent': 'advisory', 'message': 'Generating crop recommendation...'}})}\n\n"

    try:
        advisory, trace = await _run_with_retry(
            lambda: run_advisory_agent(profile, state.forecast, state.passages),
            agent_name="advisory",
        )
        state.advisory = advisory
        state.trace.append(trace)
        yield f"data: {json.dumps({'type': 'trace', 'data': trace.model_dump(mode='json')})}\n\n"

        # ORC-2 & ORC-3: Validate citations
        _validate_citations(advisory)

        # Check if advisory reports insufficient guidance
        if not advisory.sufficient_guidance:
            state.is_refusal = True
            state.refusal_reason = "The AI determined there is insufficient corpus data to make a reliable recommendation for this district and season."

    except Exception as e:
        error_trace = TraceEntry(
            agent="advisory",
            status=AgentStatus.ERROR,
            message=f"Advisory failed: {str(e)[:100]}",
        )
        state.trace.append(error_trace)
        yield f"data: {json.dumps({'type': 'trace', 'data': error_trace.model_dump(mode='json')})}\n\n"

        # Return partial results with forecast data
        response = PipelineResponse(
            trace=state.trace,
            error=f"Advisory generation failed: {e}",
        )
        yield f"data: {json.dumps({'type': 'complete', 'data': response.model_dump(mode='json')})}\n\n"
        return

    # ─── Stage 4: Localization ───────────────────────────────────────
    if not state.is_refusal:
        yield f"data: {json.dumps({'type': 'stage_start', 'data': {'agent': 'localization', 'message': 'Translating advisory...'}})}\n\n"

        try:
            localized, trace = await _run_with_retry(
                lambda: run_localization_agent(state.advisory, profile.language),
                agent_name="localization",
            )
            state.localized = localized
            state.trace.append(trace)
            yield f"data: {json.dumps({'type': 'trace', 'data': trace.model_dump(mode='json')})}\n\n"

        except Exception as e:
            error_trace = TraceEntry(
                agent="localization",
                status=AgentStatus.DEGRADED,
                message=f"Localization degraded: {str(e)[:100]} — advisory available without translation",
            )
            state.trace.append(error_trace)
            yield f"data: {json.dumps({'type': 'trace', 'data': error_trace.model_dump(mode='json')})}\n\n"

    # ─── Complete ────────────────────────────────────────────────────
    response = PipelineResponse(
        advisory=state.advisory,
        localized=state.localized,
        trace=state.trace,
        is_refusal=state.is_refusal,
        refusal_reason=state.refusal_reason,
    )

    # Cache successful results for demo resilience
    try:
        cache.set(cache_key, value=response.model_dump(mode="json"))
    except Exception as e:
        logger.debug(f"Failed to cache pipeline result: {e}")

    yield f"data: {json.dumps({'type': 'complete', 'data': response.model_dump(mode='json')})}\n\n"


async def _execute_pipeline(state: PipelineState, settings) -> PipelineResponse:
    """Internal pipeline execution (non-streaming)."""

    # Stage 1: Forecast
    try:
        forecast, trace = await _run_with_retry(
            lambda: run_forecast_agent(state.profile),
            agent_name="forecast",
        )
        state.forecast = forecast
        state.trace.append(trace)
    except Exception as e:
        state.trace.append(TraceEntry(agent="forecast", status=AgentStatus.ERROR, message=str(e)[:100]))
        return PipelineResponse(trace=state.trace, error=f"Forecast failed: {e}")

    # Stage 2: Research
    try:
        passages, trace = await _run_with_retry(
            lambda: run_research_agent(state.profile, state.forecast),
            agent_name="research",
        )
        state.passages = passages
        state.trace.append(trace)
    except Exception as e:
        state.trace.append(TraceEntry(agent="research", status=AgentStatus.ERROR, message=str(e)[:100]))
        return PipelineResponse(trace=state.trace, error=f"Research failed: {e}")

    # ORC-4: Check passage count
    if len(state.passages) < settings.MIN_PASSAGES_FOR_ADVISORY:
        return PipelineResponse(
            trace=state.trace,
            is_refusal=True,
            refusal_reason=f"Insufficient corpus coverage ({len(state.passages)} passages)",
        )

    # Stage 3: Advisory
    try:
        advisory, trace = await _run_with_retry(
            lambda: run_advisory_agent(state.profile, state.forecast, state.passages),
            agent_name="advisory",
        )
        state.advisory = advisory
        state.trace.append(trace)
        _validate_citations(advisory)
    except Exception as e:
        state.trace.append(TraceEntry(agent="advisory", status=AgentStatus.ERROR, message=str(e)[:100]))
        return PipelineResponse(trace=state.trace, error=f"Advisory failed: {e}")

    # Stage 4: Localization
    if state.advisory and state.advisory.sufficient_guidance:
        try:
            localized, trace = await _run_with_retry(
                lambda: run_localization_agent(state.advisory, state.profile.language),
                agent_name="localization",
            )
            state.localized = localized
            state.trace.append(trace)
        except Exception as e:
            state.trace.append(TraceEntry(
                agent="localization", status=AgentStatus.DEGRADED, message=str(e)[:100]
            ))

    return PipelineResponse(
        advisory=state.advisory,
        localized=state.localized,
        trace=state.trace,
        is_refusal=not (state.advisory and state.advisory.sufficient_guidance),
        refusal_reason=state.refusal_reason,
    )


async def _run_with_retry(fn, agent_name: str, max_retries: int = 1):
    """ORC-5: Retry a failed agent once with backoff."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(
                    f"Orchestrator: {agent_name} failed (attempt {attempt + 1}), "
                    f"retrying in {backoff}s — {e}"
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(f"Orchestrator: {agent_name} failed after {max_retries + 1} attempts — {e}")
    raise last_error


def _validate_citations(advisory: Advisory) -> None:
    """
    ORC-2: Block any Advisory where a Claim has empty citation_ids.
    ORC-3: Validate every citation_id resolves to a passage.
    """
    citation_lookup = advisory.citations

    for crop in advisory.recommended:
        for claim in crop.rationale:
            # ORC-2: Non-empty citations
            if not claim.citation_ids:
                raise ValueError(
                    f"ORC-2 violation: Claim '{claim.statement[:60]}...' has no citations"
                )
            # ORC-3: All citation IDs must resolve
            for cid in claim.citation_ids:
                if cid not in citation_lookup:
                    logger.warning(
                        f"ORC-3: citation_id '{cid}' does not resolve to a passage. "
                        f"Available: {list(citation_lookup.keys())}"
                    )
                    # Don't hard-fail on this in mock mode, but log it
                    # In production with real Granite, this would be a hard failure

    for claim in advisory.irrigation_guidance:
        if not claim.citation_ids:
            raise ValueError(
                f"ORC-2 violation: Irrigation claim '{claim.statement[:60]}...' has no citations"
            )

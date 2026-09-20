"""
Unit tests for Orchestrator Agent (T5 & T8).
- T5: Refusal path fires when corpus is stripped / passages < threshold
- T8: Pipeline timeout produces partial result with timeout status
- Invariant tests for ORC-2 and ORC-3
"""

import asyncio
from unittest.mock import patch

from app.contracts import (
    FarmerProfile,
    Season,
    IrrigationAccess,
    PipelineResponse,
    AgentStatus,
)
from app.agents.orchestrator import run_pipeline, _validate_citations


def test_t5_refusal_path_on_insufficient_passages():
    """
    T5: When Research returns fewer than MIN_PASSAGES, the orchestrator
    must set is_refusal=True, refusal_reason, and not call Advisory.
    """
    profile = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=2.0,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
    )

    from app.contracts import RetrievedPassage, TraceEntry

    single_passage = [
        RetrievedPassage(
            passage_id="P-test1",
            text="Very sparse information with no clear guidance.",
            relevance_score=0.4,
            doc_title="Generic Note",
            publishing_body="Unknown",
            source_uri="file://test.pdf",
        )
    ]

    async def mock_research(*args, **kwargs):
        return single_passage, TraceEntry(agent="research", status=AgentStatus.OK, ms=10)

    with patch("app.agents.orchestrator.run_research_agent", side_effect=mock_research):
        response = asyncio.run(run_pipeline(profile))

        assert response.is_refusal is True
        assert response.refusal_reason is not None
        assert "insufficient" in response.refusal_reason.lower()
        assert response.advisory is None


def test_t8_pipeline_timeout_handling():
    """
    T8: When an agent hangs or takes longer than timeout, orchestrator returns
    a partial PipelineResponse with timeout status rather than crashing.
    """
    profile = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=2.0,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
    )

    async def slow_research(*args, **kwargs):
        await asyncio.sleep(2)
        return [], None

    with patch("app.agents.orchestrator.run_research_agent", side_effect=slow_research):
        with patch("app.agents.orchestrator.get_settings") as mock_settings:
            from app.config import Settings
            s = Settings(PIPELINE_TIMEOUT_S=1)
            mock_settings.return_value = s

            response = asyncio.run(run_pipeline(profile))
            assert response is not None
            assert response.error is not None
            assert "timed out" in response.error.lower()
            timeout_traces = [t for t in response.trace if t.status == AgentStatus.TIMEOUT]
            assert len(timeout_traces) > 0

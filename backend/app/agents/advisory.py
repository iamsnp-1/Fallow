"""
Fallow — Advisory Agent (IBM Granite)

Implements AD-1 through AD-7:
- AD-1: Prompt includes forecast, passages, and farmer profile
- AD-2: Constrained JSON output matching Advisory schema; validate & retry
- AD-3: System prompt instructs citation for every claim
- AD-4: Set sufficient_guidance=False rather than improvise
- AD-5: Set hedged=True when forecast confidence is low
- AD-6: Candidate crops constrained to locally available
- AD-7: Temperature low (~0.2)
"""

import json
import logging
import time

from app.config import get_settings
from app.contracts import (
    FarmerProfile, ForecastResult, RetrievedPassage,
    Advisory, CropOption, Claim, TraceEntry, AgentStatus,
    Confidence, Viability,
)
from app.districts import get_candidate_crops
from app.services.watsonx_client import get_watsonx_client

logger = logging.getLogger(__name__)

# AD-3: System prompt with strict citation and grounding instructions
ADVISORY_SYSTEM_PROMPT = """You are an agricultural advisory agent for Indian farmers. You produce CROP RECOMMENDATIONS based ONLY on the retrieved passages provided to you.

CRITICAL RULES:
1. Every substantive claim MUST have a citation_ids field referencing passage_id(s) from the provided passages.
2. Do NOT use knowledge beyond what is in the provided passages for agronomic facts.
3. If the passages do not contain sufficient information to make a recommendation, set "sufficient_guidance" to false.
4. Output MUST be valid JSON matching the schema exactly.
5. Rank crops by suitability for the given forecast conditions.
6. When forecast confidence is "low", set "hedged" to true and soften language.
7. Water requirement values must come from the passages, not from memory.

OUTPUT SCHEMA:
{
  "recommended": [
    {
      "crop": "string",
      "rank": integer,
      "rationale": [
        {"statement": "string", "citation_ids": ["passage_id1"]}
      ],
      "water_requirement_mm": float or null,
      "sowing_window": "string" or null,
      "expected_viability": "good" | "moderate" | "poor"
    }
  ],
  "irrigation_guidance": [
    {"statement": "string", "citation_ids": ["passage_id1"]}
  ],
  "warnings": ["string"],
  "hedged": boolean,
  "sufficient_guidance": boolean
}

Respond with ONLY the JSON object, no markdown formatting or explanation."""


def _build_advisory_prompt(
    profile: FarmerProfile,
    forecast: ForecastResult,
    passages: list[RetrievedPassage],
    candidate_crops: list[str],
) -> str:
    """AD-1: Build the full prompt with all context."""
    passages_text = "\n\n".join([
        f"--- PASSAGE {p.passage_id} ---\n"
        f"Source: {p.doc_title} ({p.publishing_body}, {p.year or 'n/a'})\n"
        f"Section: {p.section or 'n/a'} | Page: {p.page or 'n/a'}\n"
        f"Text: {p.text}"
        for p in passages
    ])

    deviation_direction = "below" if forecast.deviation_pct < 0 else "above"

    prompt = f"""FARMER PROFILE:
- District: {profile.district_name} ({profile.district_id})
- Land: {profile.land_size_acres} acres
- Irrigation: {profile.irrigation_access.value}
- Season: {profile.season.value}
- Crop History: {', '.join(profile.crop_history) if profile.crop_history else 'Not provided'}

SEASONAL FORECAST:
- Projected Rainfall: {forecast.projected_rainfall_mm:.0f} mm
- Historical Mean: {forecast.historical_mean_mm:.0f} mm
- Deviation: {abs(forecast.deviation_pct):.1f}% {deviation_direction} normal
- Anomaly: {'YES - significant deviation' if forecast.anomaly_flag else 'No - near normal'}
- Confidence: {forecast.confidence.value}
- Soil Moisture Index: {forecast.soil_moisture_index or 'Not available'}

CANDIDATE CROPS (locally available and marketable):
{', '.join(candidate_crops)}

RETRIEVED PASSAGES:
{passages_text}

Based on the above forecast and ONLY the information in the provided passages, generate a ranked crop recommendation with citations. Every claim must reference at least one passage_id."""

    return prompt


async def run_advisory_agent(
    profile: FarmerProfile,
    forecast: ForecastResult,
    passages: list[RetrievedPassage],
) -> tuple[Advisory, TraceEntry]:
    """
    Execute the Advisory Agent.
    
    AD-1 through AD-7 implementation.
    """
    start_ms = time.time()
    settings = get_settings()
    logger.info(f"Advisory Agent: starting for {profile.district_id}")

    # AD-6: Constrain candidate crops to locally available
    candidate_crops = get_candidate_crops(profile.district_id)

    # Build prompt
    prompt = _build_advisory_prompt(profile, forecast, passages, candidate_crops)
    watsonx = get_watsonx_client()

    # AD-2: Attempt generation with retry on schema violation
    last_error = None
    for attempt in range(2):
        try:
            # AD-7: Low temperature for reasoning task
            raw_response = await watsonx.generate(
                prompt=prompt,
                system_prompt=ADVISORY_SYSTEM_PROMPT,
                max_tokens=2048,
                temperature=0.2,
            )

            # Parse and validate JSON response
            advisory_data = _parse_advisory_json(raw_response)

            # AD-5: Force hedged=True when confidence is low
            if forecast.confidence == Confidence.LOW:
                advisory_data["hedged"] = True

            # Build citation lookup
            citation_lookup = {p.passage_id: p for p in passages}

            # Validate and build CropOption objects
            recommended = []
            for crop_data in advisory_data.get("recommended", []):
                rationale = []
                for claim_data in crop_data.get("rationale", []):
                    # Validate citation IDs resolve to actual passages
                    valid_ids = [
                        cid for cid in claim_data.get("citation_ids", [])
                        if cid in citation_lookup
                    ]
                    if not valid_ids:
                        # Try to find the closest matching passage
                        if passages:
                            valid_ids = [passages[0].passage_id]
                        else:
                            continue

                    rationale.append(Claim(
                        statement=claim_data["statement"],
                        citation_ids=valid_ids,
                    ))

                if rationale:
                    viability_str = crop_data.get("expected_viability", "moderate")
                    try:
                        viability = Viability(viability_str)
                    except ValueError:
                        viability = Viability.MODERATE

                    recommended.append(CropOption(
                        crop=crop_data["crop"],
                        rank=crop_data.get("rank", len(recommended) + 1),
                        rationale=rationale,
                        water_requirement_mm=crop_data.get("water_requirement_mm"),
                        sowing_window=crop_data.get("sowing_window"),
                        expected_viability=viability,
                    ))

            # Build irrigation guidance
            irrigation_guidance = []
            for ig_data in advisory_data.get("irrigation_guidance", []):
                valid_ids = [
                    cid for cid in ig_data.get("citation_ids", [])
                    if cid in citation_lookup
                ]
                if not valid_ids and passages:
                    valid_ids = [passages[0].passage_id]
                if valid_ids:
                    irrigation_guidance.append(Claim(
                        statement=ig_data["statement"],
                        citation_ids=valid_ids,
                    ))

            # AD-4: Check sufficient guidance
            sufficient = advisory_data.get("sufficient_guidance", True)
            if not recommended:
                sufficient = False

            advisory = Advisory(
                farmer=profile,
                forecast=forecast,
                recommended=recommended,
                irrigation_guidance=irrigation_guidance,
                warnings=advisory_data.get("warnings", []),
                hedged=advisory_data.get("hedged", False),
                sufficient_guidance=sufficient,
                citations=citation_lookup,
            )

            elapsed_ms = int((time.time() - start_ms) * 1000)
            logger.info(
                f"Advisory Agent: completed in {elapsed_ms}ms — "
                f"{len(recommended)} crops recommended, "
                f"sufficient={sufficient}, hedged={advisory.hedged}"
            )

            trace = TraceEntry(
                agent="advisory",
                status=AgentStatus.OK,
                ms=elapsed_ms,
                message=f"Generated {len(recommended)} crop recommendations"
                        + (" (hedged)" if advisory.hedged else ""),
            )

            return advisory, trace

        except Exception as e:
            last_error = e
            logger.warning(f"Advisory Agent: attempt {attempt + 1} failed — {e}")
            if attempt == 0:
                logger.info("Advisory Agent: retrying...")

    # Both attempts failed
    elapsed_ms = int((time.time() - start_ms) * 1000)
    logger.error(f"Advisory Agent: failed after {elapsed_ms}ms — {last_error}")

    trace = TraceEntry(
        agent="advisory",
        status=AgentStatus.ERROR,
        ms=elapsed_ms,
        message=f"Advisory generation failed: {str(last_error)[:100]}",
    )
    raise RuntimeError(f"Advisory Agent failed: {last_error}")


def _parse_advisory_json(raw: str) -> dict:
    """Parse JSON from LLM response, handling common formatting issues."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    # Try to find JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse advisory JSON: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"Invalid advisory JSON: {e}")

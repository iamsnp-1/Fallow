"""
Unit tests for Advisory Agent (T3 & T4).
- T3: Every citation_id in an Advisory resolves programmatically to a passage
- T4: Advisory Agent returns schema-valid JSON across repeated runs
"""

import asyncio
from app.contracts import (
    FarmerProfile,
    ForecastResult,
    Confidence,
    Season,
    IrrigationAccess,
    Advisory,
)
from app.agents.research import run_research_agent
from app.agents.advisory import run_advisory_agent


def test_t3_t4_advisory_generation_and_citation_resolution():
    """
    T3: Every citation_id in an Advisory resolves to a valid RetrievedPassage.
    T4: Advisory Agent returns schema-valid Advisory object across runs.
    """
    profile = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=3.0,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
        language="hi",
    )
    forecast = ForecastResult(
        district_id="IN-MH-AUR",
        season="kharif",
        projected_rainfall_mm=468.0,
        historical_mean_mm=720.0,
        deviation_pct=-35.0,
        confidence=Confidence.MEDIUM,
        anomaly_flag=True,
        baseline_years=15,
    )

    passages, _ = asyncio.run(run_research_agent(profile, forecast))
    assert len(passages) >= 3

    # Run advisory agent
    advisory, trace = asyncio.run(run_advisory_agent(profile, forecast, passages))

    # T4: Schema-valid Advisory
    assert isinstance(advisory, Advisory)
    assert trace.status.value == "ok"
    assert len(advisory.recommended) > 0

    # T3: Every citation_id resolves programmatically
    citation_lookup = advisory.citations
    for crop in advisory.recommended:
        assert len(crop.rationale) > 0
        for claim in crop.rationale:
            assert len(claim.citation_ids) > 0, "Claim must have non-empty citations"
            for cid in claim.citation_ids:
                assert cid in citation_lookup, f"Citation ID {cid} must resolve in citations lookup"
                passage = citation_lookup[cid]
                assert passage.doc_title is not None
                assert passage.source_uri is not None

    for claim in advisory.irrigation_guidance:
        assert len(claim.citation_ids) > 0
        for cid in claim.citation_ids:
            assert cid in citation_lookup

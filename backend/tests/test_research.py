"""
Unit tests for Research Agent (RAG retrieval and provenance, T2).
"""

import asyncio
from app.contracts import FarmerProfile, ForecastResult, Confidence, Season, IrrigationAccess
from app.agents.research import run_research_agent, build_research_query, DEMO_PASSAGES


def test_t2_query_construction():
    """RS-4: Query construction includes district, season, agro-climatic zone, and candidate crops."""
    profile = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=2.0,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
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

    query = build_research_query(profile, forecast)
    assert "Aurangabad" in query or "IN-MH-AUR" in query or "kharif" in query.lower()
    assert "deficit" in query.lower() or "drought" in query.lower() or "rainfall" in query.lower()


def test_t2_research_agent_returns_valid_passages():
    """RS-7: Retrieved passages must include full provenance and non-empty text."""
    profile = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=2.0,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
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

    passages, trace = asyncio.run(run_research_agent(profile, forecast))
    assert len(passages) >= 3
    assert trace.status.value == "ok"

    for p in passages:
        assert p.passage_id.startswith("P-")
        assert len(p.text) > 20
        assert p.publishing_body is not None
        assert p.source_uri is not None
        assert p.relevance_score >= 0.35  # RS-6 relevance floor

"""
Integration tests for End-to-End Pipeline (T6 & T7).
- T6: Two contrasting districts produce materially different recommendations
- T7: External API failure degrades gracefully without crashing
"""

import asyncio
from unittest.mock import patch

from app.contracts import FarmerProfile, Season, IrrigationAccess
from app.agents.orchestrator import run_pipeline


def test_t6_contrasting_districts_recommendation_divergence():
    """
    T6: Aurangabad (drought/semi-arid) vs Thanjavur (delta/irrigated) must
    produce materially different crop recommendations.
    """
    profile_aur = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=3.0,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
        language="mr",
    )

    profile_tnj = FarmerProfile(
        district_id="IN-TN-TNJ",
        district_name="Thanjavur",
        land_size_acres=3.0,
        irrigation_access=IrrigationAccess.CANAL,
        season=Season.KHARIF,
        language="ta",
    )

    res_aur = asyncio.run(run_pipeline(profile_aur))
    res_tnj = asyncio.run(run_pipeline(profile_tnj))

    assert res_aur.advisory is not None
    assert res_tnj.advisory is not None

    aur_crops = {c.crop.lower() for c in res_aur.advisory.recommended}
    tnj_crops = {c.crop.lower() for c in res_tnj.advisory.recommended}

    # Verify material divergence
    # Aurangabad should feature drought-tolerant dryland crops like bajra, jowar, or tur
    aur_targets = ["bajra", "jowar", "tur", "mung", "soybean", "cotton"]
    assert any(any(target in c for target in aur_targets) for c in aur_crops)
    # Thanjavur should feature delta crops like rice, blackgram, greengram, or sesame
    tnj_targets = ["rice", "blackgram", "greengram", "sesame", "sugarcane"]
    assert any(any(target in c for target in tnj_targets) for c in tnj_crops)

    # They should not recommend identical top crops
    top_aur = res_aur.advisory.recommended[0].crop.lower()
    top_tnj = res_tnj.advisory.recommended[0].crop.lower()
    assert top_aur != top_tnj, f"Top crops must differ ({top_aur} vs {top_tnj})"


def test_t7_external_api_failure_graceful_degradation():
    """
    T7: Injected failure in weather API falls back to cached/demo data
    and pipeline completes without crashing.
    """
    profile = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=2.0,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
        language="hi",
    )

    # Force weather fetch error to trigger demo fallback
    with patch("app.services.weather._fetch_historical_rainfall", side_effect=RuntimeError("Weather API Down")):
        response = asyncio.run(run_pipeline(profile))
        # Should not crash, should succeed via demo fallback
        assert response is not None
        assert response.advisory is not None
        assert len(response.advisory.recommended) > 0

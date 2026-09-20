"""
Unit tests for Forecast Agent and deviation computation (T1).
"""

import asyncio
from app.contracts import FarmerProfile, Season, IrrigationAccess
from app.agents.forecast import run_forecast_agent
from app.services.weather import compute_deviation, DEMO_FORECAST_DATA


def test_t1_deviation_computation():
    """
    T1: Deviation computation verified against known figures:
    historical_mean = 720.0 mm
    projected = 468.0 mm
    deviation = (468.0 - 720.0) / 720.0 * 100 = -35.0%
    """
    projected = 468.0
    baseline = 720.0
    deviation = compute_deviation(projected, baseline)
    assert round(deviation, 1) == -35.0

    # Surplus case: 600 projected vs 500 baseline -> +20%
    assert round(compute_deviation(600.0, 500.0), 1) == 20.0

    # Zero baseline edge case handling
    assert compute_deviation(100.0, 0.0) == 0.0


def test_forecast_agent_aurangabad_anomaly():
    """Aurangabad Kharif forecast should detect deficit anomaly."""
    profile = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=2.5,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
    )

    forecast, trace = asyncio.run(run_forecast_agent(profile))
    assert forecast.district_id == "IN-MH-AUR"
    assert forecast.anomaly_flag is True
    assert forecast.deviation_pct < -20.0
    assert trace.status.value == "ok"
    assert len(forecast.forecast_data) > 0
    assert len(forecast.historical_data) > 0

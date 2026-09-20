"""
Fallow — Forecast Agent

Implements FC-1 through FC-6:
- FC-1: Resolve district_id to lat/long centroid
- FC-2: Fetch seasonal forecast rainfall
- FC-3: Fetch historical baseline (10+ years)
- FC-4: Compute deviation_pct; set anomaly_flag
- FC-5: Derive confidence from forecast horizon
- FC-6: Cache responses by (district_id, season)
"""

import logging
import time

from app.contracts import FarmerProfile, ForecastResult, TraceEntry, AgentStatus
from app.services.weather import fetch_forecast

logger = logging.getLogger(__name__)


async def run_forecast_agent(profile: FarmerProfile) -> tuple[ForecastResult, TraceEntry]:
    """
    Execute the Forecast Agent.
    
    Input: FarmerProfile with district_id and season
    Output: ForecastResult with deviation, anomaly flag, confidence
    """
    start_ms = time.time()
    logger.info(f"Forecast Agent: starting for {profile.district_id}, season={profile.season}")

    try:
        result = await fetch_forecast(profile.district_id, profile.season.value)

        elapsed_ms = int((time.time() - start_ms) * 1000)
        logger.info(
            f"Forecast Agent: completed in {elapsed_ms}ms — "
            f"deviation={result.deviation_pct:+.1f}%, "
            f"anomaly={result.anomaly_flag}, "
            f"confidence={result.confidence.value}"
        )

        trace = TraceEntry(
            agent="forecast",
            status=AgentStatus.OK,
            ms=elapsed_ms,
            message=f"Rainfall deviation: {result.deviation_pct:+.1f}% from {result.baseline_years}-year mean"
                    + (f" ⚠ ANOMALY" if result.anomaly_flag else ""),
        )

        return result, trace

    except Exception as e:
        elapsed_ms = int((time.time() - start_ms) * 1000)
        logger.error(f"Forecast Agent: failed after {elapsed_ms}ms — {e}")

        trace = TraceEntry(
            agent="forecast",
            status=AgentStatus.ERROR,
            ms=elapsed_ms,
            message=f"Forecast failed: {str(e)[:100]}",
        )
        raise

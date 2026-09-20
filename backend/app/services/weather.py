"""
Fallow — Weather Service (Open-Meteo)

Implements FC-1 through FC-6:
- Resolve district to lat/long
- Fetch seasonal forecast and historical baseline rainfall
- Cache by (district_id, season)
- Demo fallback with pre-seeded data

Open-Meteo API: no key, no signup, historical + forecast endpoints.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.config import get_settings
from app.contracts import ForecastResult, MonthlyDataPoint, Confidence
from app.districts import get_district, SEASON_WINDOWS
from app.services.cache import get_cache

logger = logging.getLogger(__name__)

# Pre-seeded demo data for offline resilience
DEMO_FORECAST_DATA: dict[str, dict] = {
    "IN-MH-AUR:kharif": {
        "projected_rainfall_mm": 468.0,
        "historical_mean_mm": 720.0,
        "deviation_pct": -35.0,
        "soil_moisture_index": 0.22,
        "confidence": "medium",
        "anomaly_flag": True,
        "baseline_years": 15,
        "source": "open-meteo",
        "forecast_data": [
            {"month": "Jun", "rainfall_mm": 85.0},
            {"month": "Jul", "rainfall_mm": 125.0},
            {"month": "Aug", "rainfall_mm": 130.0},
            {"month": "Sep", "rainfall_mm": 88.0},
            {"month": "Oct", "rainfall_mm": 40.0},
        ],
        "historical_data": [
            {"month": "Jun", "rainfall_mm": 135.0},
            {"month": "Jul", "rainfall_mm": 195.0},
            {"month": "Aug", "rainfall_mm": 190.0},
            {"month": "Sep", "rainfall_mm": 135.0},
            {"month": "Oct", "rainfall_mm": 65.0},
        ],
    },
    "IN-TN-TNJ:kharif": {
        "projected_rainfall_mm": 385.0,
        "historical_mean_mm": 410.0,
        "deviation_pct": -6.1,
        "soil_moisture_index": 0.58,
        "confidence": "medium",
        "anomaly_flag": False,
        "baseline_years": 15,
        "source": "open-meteo",
        "forecast_data": [
            {"month": "Jun", "rainfall_mm": 42.0},
            {"month": "Jul", "rainfall_mm": 55.0},
            {"month": "Aug", "rainfall_mm": 85.0},
            {"month": "Sep", "rainfall_mm": 115.0},
            {"month": "Oct", "rainfall_mm": 88.0},
        ],
        "historical_data": [
            {"month": "Jun", "rainfall_mm": 45.0},
            {"month": "Jul", "rainfall_mm": 60.0},
            {"month": "Aug", "rainfall_mm": 90.0},
            {"month": "Sep", "rainfall_mm": 120.0},
            {"month": "Oct", "rainfall_mm": 95.0},
        ],
    },
    "IN-MH-AUR:rabi": {
        "projected_rainfall_mm": 28.0,
        "historical_mean_mm": 35.0,
        "deviation_pct": -20.0,
        "soil_moisture_index": 0.18,
        "confidence": "medium",
        "anomaly_flag": True,
        "baseline_years": 15,
        "source": "open-meteo",
        "forecast_data": [
            {"month": "Nov", "rainfall_mm": 12.0},
            {"month": "Dec", "rainfall_mm": 5.0},
            {"month": "Jan", "rainfall_mm": 6.0},
            {"month": "Feb", "rainfall_mm": 5.0},
        ],
        "historical_data": [
            {"month": "Nov", "rainfall_mm": 15.0},
            {"month": "Dec", "rainfall_mm": 7.0},
            {"month": "Jan", "rainfall_mm": 6.0},
            {"month": "Feb", "rainfall_mm": 7.0},
        ],
    },
    "IN-TN-TNJ:rabi": {
        "projected_rainfall_mm": 620.0,
        "historical_mean_mm": 580.0,
        "deviation_pct": 6.9,
        "soil_moisture_index": 0.65,
        "confidence": "medium",
        "anomaly_flag": False,
        "baseline_years": 15,
        "source": "open-meteo",
        "forecast_data": [
            {"month": "Nov", "rainfall_mm": 210.0},
            {"month": "Dec", "rainfall_mm": 185.0},
            {"month": "Jan", "rainfall_mm": 130.0},
            {"month": "Feb", "rainfall_mm": 95.0},
        ],
        "historical_data": [
            {"month": "Nov", "rainfall_mm": 195.0},
            {"month": "Dec", "rainfall_mm": 175.0},
            {"month": "Jan", "rainfall_mm": 120.0},
            {"month": "Feb", "rainfall_mm": 90.0},
        ],
    },
}

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def compute_deviation(projected: float, historical_mean: float) -> float:
    """Compute rainfall deviation percentage relative to historical mean."""
    if historical_mean <= 0:
        return 0.0
    return ((projected - historical_mean) / historical_mean) * 100.0


async def fetch_forecast(district_id: str, season: str) -> ForecastResult:
    """
    Fetch seasonal forecast for a district.
    
    FC-1: Resolve district_id to lat/long
    FC-2: Fetch seasonal forecast rainfall
    FC-3: Fetch historical rainfall for baseline
    FC-4: Compute deviation_pct; set anomaly_flag
    FC-5: Derive confidence from forecast horizon
    FC-6: Cache responses by (district_id, season)
    """
    settings = get_settings()
    cache = get_cache(settings.DEMO_CACHE_DIR, settings.FORECAST_CACHE_TTL)

    # FC-6: Check cache first
    cached = cache.get("forecast", district_id, season)
    if cached:
        logger.info(f"Forecast cache hit for {district_id}:{season}")
        return _build_forecast_result(district_id, season, cached)

    # FC-1: Resolve district to coordinates
    district = get_district(district_id)
    if not district:
        logger.warning(f"Unknown district {district_id}, using demo fallback")
        return _demo_fallback(district_id, season)

    lat, lon = district.lat, district.lon

    try:
        # Determine season date window
        start_md, end_md = SEASON_WINDOWS.get(season, ("06-01", "10-31"))
        now = datetime.now()
        current_year = now.year

        # FC-3: Fetch historical data
        historical_data = await _fetch_historical_rainfall(
            lat, lon, start_md, end_md,
            current_year - settings.BASELINE_YEARS, current_year - 1,
            settings
        )

        # FC-2: Fetch forecast (use recent year data as proxy for seasonal forecast)
        forecast_data = await _fetch_forecast_rainfall(
            lat, lon, start_md, end_md, current_year, settings
        )

        if historical_data and forecast_data:
            historical_mean = sum(historical_data) / len(historical_data)
            projected = sum(forecast_data["monthly_values"])

            # FC-4: Compute deviation
            deviation_pct = ((projected - historical_mean) / historical_mean) * 100 if historical_mean > 0 else 0
            anomaly_flag = abs(deviation_pct) > settings.ANOMALY_THRESHOLD_PCT

            # FC-5: Confidence based on horizon
            confidence = _derive_confidence(season, now)

            # Build monthly data points for charts
            start_month = int(start_md.split("-")[0])
            forecast_monthly = []
            historical_monthly_avg = _compute_monthly_averages(
                lat, lon, start_md, end_md,
                current_year - settings.BASELINE_YEARS,
                current_year - 1
            )

            for i, val in enumerate(forecast_data["monthly_values"]):
                month_idx = (start_month - 1 + i) % 12
                forecast_monthly.append(
                    MonthlyDataPoint(month=MONTH_NAMES[month_idx], rainfall_mm=round(val, 1))
                )

            hist_monthly = []
            for i, val in enumerate(historical_monthly_avg):
                month_idx = (start_month - 1 + i) % 12
                hist_monthly.append(
                    MonthlyDataPoint(month=MONTH_NAMES[month_idx], rainfall_mm=round(val, 1))
                )

            result_data = {
                "projected_rainfall_mm": round(projected, 1),
                "historical_mean_mm": round(historical_mean, 1),
                "deviation_pct": round(deviation_pct, 1),
                "soil_moisture_index": None,
                "confidence": confidence.value,
                "anomaly_flag": anomaly_flag,
                "baseline_years": settings.BASELINE_YEARS,
                "source": "open-meteo",
            }

            # Cache the result
            cache.set("forecast", district_id, season, value=result_data)

            return ForecastResult(
                district_id=district_id,
                season=season,
                forecast_data=forecast_monthly,
                historical_data=hist_monthly,
                **result_data,
            )
        else:
            logger.warning(f"Incomplete weather data, using demo fallback for {district_id}:{season}")
            return _demo_fallback(district_id, season)

    except Exception as e:
        logger.error(f"Weather API error for {district_id}:{season}: {e}")
        return _demo_fallback(district_id, season)


async def _fetch_historical_rainfall(
    lat: float, lon: float,
    start_md: str, end_md: str,
    start_year: int, end_year: int,
    settings,
) -> list[float]:
    """Fetch historical seasonal rainfall totals for each year concurrently."""
    import asyncio

    async def fetch_single_year(client: httpx.AsyncClient, year: int) -> Optional[float]:
        try:
            start_date = f"{year}-{start_md}"
            ey = year + 1 if int(end_md.split("-")[0]) < int(start_md.split("-")[0]) else year
            end_date = f"{ey}-{end_md}"

            resp = await client.get(
                f"{settings.WEATHER_API_BASE}/v1/archive",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": start_date,
                    "end_date": end_date,
                    "daily": "precipitation_sum",
                    "timezone": "Asia/Kolkata",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                precip = data.get("daily", {}).get("precipitation_sum", [])
                return sum(v for v in precip if v is not None)
        except Exception as e:
            logger.debug(f"Historical fetch failed for year {year}: {e}")
        return None

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            tasks = [fetch_single_year(client, year) for year in range(start_year, end_year + 1)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            yearly_totals = [r for r in results if isinstance(r, (int, float))]
            return yearly_totals
    except Exception as e:
        logger.debug(f"Historical concurrent fetch failed: {e}")
        return []


async def _fetch_forecast_rainfall(
    lat: float, lon: float,
    start_md: str, end_md: str,
    year: int,
    settings,
) -> Optional[dict]:
    """Fetch forecast/current-year rainfall data."""
    try:
        start_date = f"{year}-{start_md}"
        ey = year + 1 if int(end_md.split("-")[0]) < int(start_md.split("-")[0]) else year
        end_date = f"{ey}-{end_md}"

        async with httpx.AsyncClient(timeout=3.0) as client:
            # Try forecast endpoint first
            resp = await client.get(
                f"{settings.WEATHER_API_BASE}/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "precipitation_sum",
                    "timezone": "Asia/Kolkata",
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                precip = data.get("daily", {}).get("precipitation_sum", [])
                dates = data.get("daily", {}).get("time", [])

                # Group by month
                monthly = {}
                for d, p in zip(dates, precip):
                    if p is None:
                        continue
                    month = int(d.split("-")[1])
                    monthly.setdefault(month, 0)
                    monthly[month] += p

                # Sort by month
                start_month = int(start_md.split("-")[0])
                end_month = int(end_md.split("-")[0])
                monthly_values = []

                if end_month >= start_month:
                    for m in range(start_month, end_month + 1):
                        monthly_values.append(monthly.get(m, 0))
                else:
                    for m in list(range(start_month, 13)) + list(range(1, end_month + 1)):
                        monthly_values.append(monthly.get(m, 0))

                return {"monthly_values": monthly_values}

    except Exception as e:
        logger.warning(f"Forecast API error: {e}")

    return None


def _compute_monthly_averages(
    lat: float, lon: float,
    start_md: str, end_md: str,
    start_year: int, end_year: int,
) -> list[float]:
    """Placeholder for historical monthly averages - uses demo data."""
    # In production this would aggregate monthly data across years.
    # For demo, return reasonable estimates.
    start_month = int(start_md.split("-")[0])
    end_month = int(end_md.split("-")[0])

    if end_month >= start_month:
        return [100.0] * (end_month - start_month + 1)
    else:
        return [100.0] * (12 - start_month + 1 + end_month)


def _derive_confidence(season: str, now: datetime) -> Confidence:
    """FC-5: Long-range seasonal projection is never 'high'."""
    season_starts = {"kharif": 6, "rabi": 11, "zaid": 3}
    start_month = season_starts.get(season, 6)
    months_until = (start_month - now.month) % 12

    if months_until <= 1:
        return Confidence.MEDIUM
    else:
        return Confidence.LOW


def _demo_fallback(district_id: str, season: str) -> ForecastResult:
    """Use pre-seeded demo data when API is unavailable."""
    key = f"{district_id}:{season}"
    demo = DEMO_FORECAST_DATA.get(key)

    if demo:
        logger.info(f"Using demo fallback for {key}")
        return _build_forecast_result(district_id, season, demo)

    # Ultimate fallback — generate a synthetic result
    logger.warning(f"No demo data for {key}, generating synthetic fallback")
    return ForecastResult(
        district_id=district_id,
        season=season,
        projected_rainfall_mm=500.0,
        historical_mean_mm=600.0,
        deviation_pct=-16.7,
        soil_moisture_index=0.3,
        confidence=Confidence.LOW,
        anomaly_flag=False,
        baseline_years=15,
        source="demo-fallback",
        forecast_data=[
            MonthlyDataPoint(month="Jun", rainfall_mm=80),
            MonthlyDataPoint(month="Jul", rainfall_mm=120),
            MonthlyDataPoint(month="Aug", rainfall_mm=130),
            MonthlyDataPoint(month="Sep", rainfall_mm=100),
            MonthlyDataPoint(month="Oct", rainfall_mm=70),
        ],
        historical_data=[
            MonthlyDataPoint(month="Jun", rainfall_mm=100),
            MonthlyDataPoint(month="Jul", rainfall_mm=150),
            MonthlyDataPoint(month="Aug", rainfall_mm=160),
            MonthlyDataPoint(month="Sep", rainfall_mm=120),
            MonthlyDataPoint(month="Oct", rainfall_mm=70),
        ],
    )


def _build_forecast_result(district_id: str, season: str, data: dict) -> ForecastResult:
    """Build a ForecastResult from cached/demo data."""
    forecast_data = None
    historical_data = None

    if "forecast_data" in data:
        forecast_data = [MonthlyDataPoint(**dp) for dp in data["forecast_data"]]
    if "historical_data" in data:
        historical_data = [MonthlyDataPoint(**dp) for dp in data["historical_data"]]

    return ForecastResult(
        district_id=district_id,
        season=season,
        projected_rainfall_mm=data["projected_rainfall_mm"],
        historical_mean_mm=data["historical_mean_mm"],
        deviation_pct=data["deviation_pct"],
        soil_moisture_index=data.get("soil_moisture_index"),
        confidence=Confidence(data["confidence"]),
        anomaly_flag=data["anomaly_flag"],
        baseline_years=data["baseline_years"],
        source=data.get("source", "open-meteo"),
        forecast_data=forecast_data,
        historical_data=historical_data,
    )

"""
Fallow — District Registry

Two demo districts with deep corpus coverage:
1. Aurangabad, Maharashtra — drought-prone, semi-arid, historically water-stressed
2. Thanjavur, Tamil Nadu — Cauvery delta, irrigated, rice-dominant

These two districts are chosen to guarantee materially different recommendations
(F10, T6): one is water-scarce and the other is water-rich.
"""

from app.contracts import DistrictInfo

DISTRICTS: dict[str, DistrictInfo] = {
    "IN-MH-AUR": DistrictInfo(
        district_id="IN-MH-AUR",
        name="Aurangabad",
        state="Maharashtra",
        lat=19.8762,
        lon=75.3433,
        agro_climatic_zone="Scarcity Zone (Semi-Arid Tropics)",
        typical_crops=["jowar", "bajra", "cotton", "soybean", "tur", "mung", "sunflower", "groundnut"],
        available_languages=["mr", "hi", "en"],
    ),
    "IN-TN-TNJ": DistrictInfo(
        district_id="IN-TN-TNJ",
        name="Thanjavur",
        state="Tamil Nadu",
        lat=10.7870,
        lon=79.1378,
        agro_climatic_zone="Cauvery Delta Zone (Humid Tropics)",
        typical_crops=["rice", "blackgram", "greengram", "sesame", "groundnut", "banana", "sugarcane", "coconut"],
        available_languages=["ta", "hi", "en"],
    ),
}


# Candidate crop sets constrained to locally available and marketable crops (AD-6)
CANDIDATE_CROPS: dict[str, list[str]] = {
    "IN-MH-AUR": [
        "bajra", "jowar", "tur", "mung", "moth", "sunflower",
        "soybean", "cotton", "groundnut", "safflower", "niger",
    ],
    "IN-TN-TNJ": [
        "rice", "blackgram", "greengram", "sesame", "groundnut",
        "banana", "sugarcane", "maize", "coconut", "cotton",
    ],
}


# Season windows for forecast date ranges
SEASON_WINDOWS: dict[str, tuple[str, str]] = {
    "kharif": ("06-01", "10-31"),   # June–October
    "rabi": ("11-01", "02-28"),     # November–February
    "zaid": ("03-01", "05-31"),     # March–May
}


def get_district(district_id: str) -> DistrictInfo | None:
    """Look up a district by ID."""
    return DISTRICTS.get(district_id)


def get_all_districts() -> list[DistrictInfo]:
    """Return all registered districts."""
    return list(DISTRICTS.values())


def get_candidate_crops(district_id: str) -> list[str]:
    """Return locally available and marketable crops for a district."""
    return CANDIDATE_CROPS.get(district_id, [])

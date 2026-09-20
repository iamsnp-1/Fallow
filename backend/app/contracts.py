"""
Fallow — Pydantic Data Contracts

All inter-agent communication uses these models. No agent passes free-form
strings to another agent. This is the single most important engineering
constraint — it keeps the pipeline debuggable and citations attached to claims.

Implements §3 of fallow-technical-requirements.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Enums ───────────────────────────────────────────────────────────────────

class IrrigationAccess(str, Enum):
    RAINFED = "rainfed"
    BOREWELL = "borewell"
    CANAL = "canal"
    MIXED = "mixed"


class Season(str, Enum):
    KHARIF = "kharif"
    RABI = "rabi"
    ZAID = "zaid"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Viability(str, Enum):
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"


class AgentStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"


# ─── §3.1 FarmerProfile ─────────────────────────────────────────────────────

class FarmerProfile(BaseModel):
    """Input from the farmer or extension officer."""
    district_id: str = Field(..., description="e.g. IN-MH-AUR")
    district_name: str
    land_size_acres: float = Field(..., gt=0)
    irrigation_access: IrrigationAccess
    crop_history: list[str] = Field(default_factory=list, description="Last 2-3 seasons, most recent first")
    season: Season
    language: str = Field(default="hi", description="BCP-47 language code, e.g. mr, hi, en")


# ─── §3.2 ForecastResult ────────────────────────────────────────────────────

class ForecastResult(BaseModel):
    """Output of the Forecast Agent."""
    district_id: str
    season: str
    projected_rainfall_mm: float
    historical_mean_mm: float
    deviation_pct: float = Field(..., description="Negative = deficit")
    soil_moisture_index: Optional[float] = None
    confidence: Confidence
    anomaly_flag: bool = Field(..., description="True if |deviation_pct| > threshold")
    baseline_years: int = Field(..., description="How many years the mean is computed over")
    source: str = Field(default="open-meteo", description="open-meteo | imd")
    forecast_data: Optional[list[MonthlyDataPoint]] = None
    historical_data: Optional[list[MonthlyDataPoint]] = None


class MonthlyDataPoint(BaseModel):
    """Monthly rainfall data for chart rendering."""
    month: str
    rainfall_mm: float
    label: Optional[str] = None


# Forward ref update
ForecastResult.model_rebuild()


# ─── §3.3 RetrievedPassage ──────────────────────────────────────────────────

class RetrievedPassage(BaseModel):
    """Single retrieved passage from the RAG corpus with full provenance."""
    passage_id: str = Field(default_factory=lambda: f"P-{uuid.uuid4().hex[:8]}")
    text: str
    relevance_score: float
    doc_title: str
    publishing_body: str = Field(..., description="e.g. ICAR, MPKV Rahuri KVK")
    year: Optional[int] = None
    section: Optional[str] = None
    page: Optional[int] = None
    source_uri: str = Field(..., description="Resolves to the actual document")


# ─── §3.4 Advisory ──────────────────────────────────────────────────────────

class Claim(BaseModel):
    """A single substantive claim with mandatory citation references."""
    statement: str
    citation_ids: list[str] = Field(
        ...,
        min_length=1,
        description="Must be non-empty; refs RetrievedPassage.passage_id"
    )


class CropOption(BaseModel):
    """A single crop recommendation with rationale and citations."""
    crop: str
    rank: int
    rationale: list[Claim]
    water_requirement_mm: Optional[float] = None
    sowing_window: Optional[str] = None
    expected_viability: Viability


class Advisory(BaseModel):
    """Full advisory output from the Advisory Agent."""
    farmer: FarmerProfile
    forecast: ForecastResult
    recommended: list[CropOption] = Field(..., description="Ranked crop options")
    irrigation_guidance: list[Claim]
    warnings: list[str] = Field(default_factory=list)
    hedged: bool = Field(False, description="True when forecast confidence is low")
    sufficient_guidance: bool = Field(True, description="False triggers the refusal path")
    citations: dict[str, RetrievedPassage] = Field(
        default_factory=dict,
        description="passage_id -> RetrievedPassage lookup"
    )

    @field_validator("recommended")
    @classmethod
    def validate_citations_present(cls, v: list[CropOption]) -> list[CropOption]:
        """ORC-2: Block any Advisory where a Claim has empty citation_ids."""
        for crop in v:
            for claim in crop.rationale:
                if not claim.citation_ids:
                    raise ValueError(
                        f"Claim '{claim.statement[:50]}...' has no citations. "
                        "Every substantive claim MUST have a citation."
                    )
        return v


# ─── §3.5 LocalizedAdvisory ─────────────────────────────────────────────────

class LocalizedAdvisory(BaseModel):
    """Output of the Localization Agent."""
    language: str
    full_text: str
    sms_text: str = Field(..., max_length=320, description="<= 320 chars, 2 SMS segments")
    audio_url: str
    citation_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Human-readable source names in-language"
    )


# ─── Trace & Pipeline Response ──────────────────────────────────────────────

class TraceEntry(BaseModel):
    """Single agent execution trace entry for the UI."""
    agent: str
    status: AgentStatus
    ms: int = Field(0, description="Execution time in milliseconds")
    message: Optional[str] = None
    passages: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class PipelineResponse(BaseModel):
    """Full API response for POST /api/advisory."""
    advisory: Optional[Advisory] = None
    localized: Optional[LocalizedAdvisory] = None
    trace: list[TraceEntry] = Field(default_factory=list)
    error: Optional[str] = None
    is_refusal: bool = False
    refusal_reason: Optional[str] = None


# ─── District Info ───────────────────────────────────────────────────────────

class DistrictInfo(BaseModel):
    """District metadata for the selector."""
    district_id: str
    name: str
    state: str
    lat: float
    lon: float
    agro_climatic_zone: str
    typical_crops: list[str]
    available_languages: list[str]

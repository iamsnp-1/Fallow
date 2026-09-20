"""
Fallow — Climate-Aware Crop Planning Advisory System
FastAPI Main Application Entry Point

Provides REST and SSE endpoints for:
- Advisory generation with streaming trace (ORC-6)
- Seasonal forecast retrieval
- District registry
- Citation lookup with full provenance
- Static audio serving for localized TTS
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.contracts import (
    FarmerProfile,
    ForecastResult,
    PipelineResponse,
    DistrictInfo,
    Season,
)
from app.districts import get_all_districts, get_district
from app.agents.forecast import run_forecast_agent
from app.agents.orchestrator import run_pipeline, run_pipeline_streaming
from app.agents.research import DEMO_PASSAGES
from app.ingestion.ingest_corpus import seed_demo_corpus, ingest_corpus
from app.services.vectorstore import get_vectorstore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fallow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    settings = get_settings()
    logger.info("Initializing Fallow advisory backend...")

    # Ensure required directories exist
    settings.audio_path
    settings.demo_cache_path
    settings.corpus_path

    # Seed demo corpus into vector store if empty
    try:
        seeded = await seed_demo_corpus()
        logger.info(f"Vector store ready ({seeded} passages available)")
    except Exception as e:
        logger.warning(f"Failed to seed demo corpus on startup: {e}")

    yield
    logger.info("Fallow backend shutting down.")


settings = get_settings()

app = FastAPI(
    title="Fallow API",
    description="Climate-aware crop planning agent pipeline with IBM Granite and RAG grounding",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for hackathon/local dev convenience
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static files for generated audio ────────────────────────────────────────
audio_dir = Path(settings.AUDIO_DIR)
audio_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/audio", StaticFiles(directory=str(audio_dir)), name="audio")


# ─── Health & Metadata Endpoints ─────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Fallow Climate-Aware Crop Advisory API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "demo_mode": settings.DEMO_MODE,
        "watsonx_configured": settings.has_watsonx_credentials,
    }


@app.get("/api/health")
async def health_check():
    store = get_vectorstore()
    return {
        "status": "healthy",
        "watsonx_configured": settings.has_watsonx_credentials,
        "demo_mode": settings.DEMO_MODE,
        "corpus_passages": store.count,
        "supported_districts": len(get_all_districts()),
    }


@app.get("/api/districts", response_model=list[DistrictInfo])
async def list_districts():
    """Return all supported demo districts with agro-climatic zones and typical crops."""
    return get_all_districts()


# ─── Forecast Endpoint ───────────────────────────────────────────────────────

@app.get("/api/forecast/{district_id}", response_model=ForecastResult)
async def get_district_forecast(
    district_id: str,
    season: Season = Season.KHARIF,
):
    """
    Fetch seasonal forecast and historical deviation baseline for a district.
    """
    district = get_district(district_id)
    if not district:
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")

    mock_profile = FarmerProfile(
        district_id=district_id,
        district_name=district.name,
        land_size_acres=2.0,
        irrigation_access="rainfed",
        season=season,
        language="hi",
    )

    forecast_result, _ = await run_forecast_agent(mock_profile)
    return forecast_result


# ─── Advisory Pipeline Endpoint ──────────────────────────────────────────────

@app.post("/api/advisory")
async def generate_advisory(
    profile: FarmerProfile,
    stream: bool = Query(default=True, description="Stream SSE trace events"),
):
    """
    Generate climate-aware crop advisory for a farmer profile.
    
    Supports:
    - SSE streaming (stream=true, default): yields stage_start, trace, forecast, error, complete events
    - Synchronous JSON (stream=false): returns PipelineResponse
    """
    district = get_district(profile.district_id)
    if not district:
        raise HTTPException(status_code=404, detail=f"District {profile.district_id} not found")

    if stream:
        return StreamingResponse(
            run_pipeline_streaming(profile),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        response = await run_pipeline(profile)
        return response


# ─── Citation & Provenance Endpoint ──────────────────────────────────────────

@app.get("/api/citation/{passage_id}")
async def get_citation(passage_id: str):
    """
    Lookup a citation passage by passage_id to view full provenance and text.
    First checks vector store, then demo passages registry.
    """
    # 1. Search vectorstore
    store = get_vectorstore()
    doc = await store.get_by_id(passage_id)
    if doc:
        return doc

    # 2. Search DEMO_PASSAGES fallback
    for district_id, passages in DEMO_PASSAGES.items():
        for p in passages:
            if p["passage_id"] == passage_id:
                return {
                    "id": p["passage_id"],
                    "text": p["text"],
                    "metadata": {
                        "doc_title": p["doc_title"],
                        "publishing_body": p["publishing_body"],
                        "year": p.get("year"),
                        "section": p.get("section"),
                        "page": p.get("page"),
                        "source_uri": p["source_uri"],
                        "relevance_score": p.get("relevance_score", 1.0),
                        "district_id": district_id,
                    },
                }

    raise HTTPException(status_code=404, detail=f"Citation {passage_id} not found")


# ─── Audio Endpoint Fallback ─────────────────────────────────────────────────

@app.get("/api/audio/{filename}")
async def get_audio_file(filename: str):
    """Direct audio file download/streaming endpoint."""
    file_path = settings.audio_path / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(file_path), media_type="audio/mpeg")


# ─── Corpus Ingestion Endpoint ───────────────────────────────────────────────

@app.post("/api/ingest")
async def trigger_ingest(corpus_dir: Optional[str] = None):
    """Trigger PDF ingestion from corpus directory."""
    target_dir = corpus_dir or settings.CORPUS_DIR
    count = await ingest_corpus(target_dir)
    return {
        "status": "success",
        "ingested_chunks": count,
        "corpus_dir": target_dir,
    }

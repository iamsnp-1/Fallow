"""
Fallow — Application Configuration

Every threshold is configurable via environment variables.
None are hardcoded in source code.
Implements §7 of fallow-technical-requirements.md.
"""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ─── IBM watsonx.ai ──────────────────────────────────────────────────
    WATSONX_API_KEY: str = ""
    WATSONX_PROJECT_ID: str = ""
    WATSONX_URL: str = "https://us-south.ml.cloud.ibm.com"
    GRANITE_MODEL_ID: str = "ibm/granite-3-8b-instruct"
    EMBEDDING_MODEL_ID: str = "ibm/slate-125m-english-rtrvr"

    # ─── ChromaDB ────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CORPUS_DIR: str = "./data/corpus"

    # ─── Weather API ─────────────────────────────────────────────────────
    WEATHER_API_BASE: str = "https://api.open-meteo.com"
    FORECAST_CACHE_TTL: int = 3600

    # ─── Pipeline thresholds ─────────────────────────────────────────────
    ANOMALY_THRESHOLD_PCT: float = 20.0
    BASELINE_YEARS: int = 15
    RETRIEVAL_TOP_K: int = 8
    RELEVANCE_FLOOR: float = 0.35
    MIN_PASSAGES_FOR_ADVISORY: int = 3
    PIPELINE_TIMEOUT_S: int = 30

    # ─── Paths ───────────────────────────────────────────────────────────
    AUDIO_DIR: str = "./data/audio"
    DEMO_CACHE_DIR: str = "./data/demo_cache"
    SEED_DATA_DIR: str = "./data/seed"

    # ─── Server ──────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ─── Demo mode ───────────────────────────────────────────────────────
    DEMO_MODE: bool = False  # When True, uses cached responses for everything

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def chroma_path(self) -> Path:
        return Path(self.CHROMA_PERSIST_DIR)

    @property
    def corpus_path(self) -> Path:
        return Path(self.CORPUS_DIR)

    @property
    def audio_path(self) -> Path:
        p = Path(self.AUDIO_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def demo_cache_path(self) -> Path:
        p = Path(self.DEMO_CACHE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def has_watsonx_credentials(self) -> bool:
        return bool(self.WATSONX_API_KEY and self.WATSONX_PROJECT_ID)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()

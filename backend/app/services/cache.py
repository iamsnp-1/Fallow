"""
Fallow — Caching Service

In-memory + file-based caching for demo resilience.
Pre-seeded cache ensures the demo survives venue wifi failure.
"""

import json
import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FallowCache:
    """Two-tier cache: in-memory (fast) + file-based (persistent/demo)."""

    def __init__(self, cache_dir: str = "./data/demo_cache", ttl: int = 3600):
        self._memory: dict[str, tuple[float, Any]] = {}
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl

    @staticmethod
    def _make_key(*parts: str) -> str:
        raw = ":".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, *key_parts: str) -> Optional[Any]:
        """Look up cache: memory first, then file."""
        key = self._make_key(*key_parts)

        # Memory cache
        if key in self._memory:
            ts, val = self._memory[key]
            if time.time() - ts < self._ttl:
                logger.debug(f"Cache HIT (memory): {key}")
                return val
            else:
                del self._memory[key]

        # File cache (no TTL — demo cache is permanent)
        file_path = self._cache_dir / f"{key}.json"
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                self._memory[key] = (time.time(), data)
                logger.debug(f"Cache HIT (file): {key}")
                return data
            except Exception as e:
                logger.warning(f"Cache file read error for {key}: {e}")

        logger.debug(f"Cache MISS: {key}")
        return None

    def set(self, *key_parts: str, value: Any) -> None:
        """Store in both memory and file cache."""
        key = self._make_key(*key_parts)
        self._memory[key] = (time.time(), value)

        file_path = self._cache_dir / f"{key}.json"
        try:
            file_path.write_text(
                json.dumps(value, default=str, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.debug(f"Cache SET: {key}")
        except Exception as e:
            logger.warning(f"Cache file write error for {key}: {e}")

    def set_demo(self, *key_parts: str, value: Any) -> None:
        """Explicitly seed the file cache for demo fallback."""
        self.set(*key_parts, value=value)
        logger.info(f"Demo cache seeded: {self._make_key(*key_parts)}")


# Singleton
_cache_instance: Optional[FallowCache] = None


def get_cache(cache_dir: str = "./data/demo_cache", ttl: int = 3600) -> FallowCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = FallowCache(cache_dir=cache_dir, ttl=ttl)
    return _cache_instance

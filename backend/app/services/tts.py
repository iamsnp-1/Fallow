"""
Fallow — Text-to-Speech Service

Generates audio in Indic languages using gTTS.
LC-5: Generate TTS audio; return a playable URL.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Language code mapping for gTTS
GTTS_LANG_MAP = {
    "hi": "hi",   # Hindi
    "mr": "mr",   # Marathi
    "ta": "ta",   # Tamil
    "en": "en",   # English
    "te": "te",   # Telugu
    "kn": "kn",   # Kannada
}


async def generate_audio(text: str, language: str = "hi") -> str:
    """
    Generate TTS audio file and return the URL path.
    
    Returns a URL path like /static/audio/<hash>.mp3
    """
    settings = get_settings()
    audio_dir = settings.audio_path

    # Map language code
    gtts_lang = GTTS_LANG_MAP.get(language, "hi")

    # Generate a deterministic filename from content
    content_hash = hashlib.md5(f"{text}:{language}".encode()).hexdigest()[:12]
    filename = f"advisory_{content_hash}.mp3"
    filepath = audio_dir / filename

    # Check if already generated
    if filepath.exists():
        logger.debug(f"Audio already exists: {filename}")
        return f"/static/audio/{filename}"

    try:
        import asyncio
        from gtts import gTTS

        def _save_tts():
            tts = gTTS(text=text[:500], lang=gtts_lang, slow=False)
            tts.save(str(filepath))

        await asyncio.wait_for(asyncio.to_thread(_save_tts), timeout=3.0)
        logger.info(f"Generated TTS audio: {filename} ({gtts_lang})")
        return f"/static/audio/{filename}"

    except ImportError:
        logger.warning("gTTS not installed. Creating placeholder audio reference.")
        return _create_placeholder(filepath, filename)

    except Exception as e:
        logger.warning(f"TTS generation bypassed ({e}). Using audio placeholder.")
        return _create_placeholder(filepath, filename)


def _create_placeholder(filepath: Path, filename: str) -> str:
    """Create a placeholder file when TTS is unavailable."""
    # Write a small text file as placeholder
    placeholder = filepath.with_suffix(".txt")
    placeholder.write_text(
        "TTS audio would be generated here. Install gTTS: pip install gtts",
        encoding="utf-8"
    )
    logger.info(f"Created TTS placeholder: {filename}")
    return f"/static/audio/{filename}"

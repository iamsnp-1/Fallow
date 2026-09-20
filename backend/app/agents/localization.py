"""
Fallow — Localization & Delivery Agent

Implements LC-1 through LC-6:
- LC-1: Input is the structured Advisory object, not generated prose
- LC-2: Render via templates populated from structure
- LC-3: Output spoken register, not literal translation
- LC-4: Generate sms_text <= 320 characters
- LC-5: Generate TTS audio; return a playable URL
- LC-6: Preserve citation references as human-readable source names
"""

import json
import logging
import time

from app.contracts import (
    Advisory, LocalizedAdvisory, TraceEntry, AgentStatus,
    Confidence,
)
from app.services.watsonx_client import get_watsonx_client
from app.services.tts import generate_audio

logger = logging.getLogger(__name__)


# LC-2: Language templates for structured rendering
TEMPLATES = {
    "hi": {
        "header": "🌾 फसल सलाह — {district} जिला, {season} मौसम",
        "forecast_warning": "⚠️ चेतावनी: इस मौसम में {deviation_dir} {deviation_abs:.0f}% बारिश अपेक्षित है (अनुमानित: {projected:.0f} मिमी, सामान्य: {historical:.0f} मिमी)",
        "forecast_normal": "✅ इस मौसम में लगभग सामान्य बारिश अपेक्षित है (अनुमानित: {projected:.0f} मिमी)",
        "crop_header": "\n📋 फसल सिफारिश:",
        "crop_item": "\n{rank}. {crop} — {viability}\n   कारण: {rationale}\n   पानी: {water_req}\n   बुवाई: {sowing}",
        "irrigation_header": "\n💧 सिंचाई मार्गदर्शन:",
        "warning_header": "\n⚠️ चेतावनी:",
        "source_header": "\n📚 स्रोत:",
        "viability_map": {"good": "अच्छी उपयुक्तता", "moderate": "मध्यम उपयुक्तता", "poor": "कम उपयुक्तता"},
        "deviation_below": "सामान्य से कम",
        "deviation_above": "सामान्य से अधिक",
    },
    "mr": {
        "header": "🌾 पीक सल्ला — {district} जिल्हा, {season} हंगाम",
        "forecast_warning": "⚠️ इशारा: या हंगामात सरासरीपेक्षा {deviation_abs:.0f}% {deviation_dir} पाऊस अपेक्षित आहे (अंदाज: {projected:.0f} मिमी, सरासरी: {historical:.0f} मिमी)",
        "forecast_normal": "✅ या हंगामात जवळपास सरासरी पाऊस अपेक्षित आहे (अंदाज: {projected:.0f} मिमी)",
        "crop_header": "\n📋 पीक शिफारस:",
        "crop_item": "\n{rank}. {crop} — {viability}\n   कारण: {rationale}\n   पाणी: {water_req}\n   पेरणी: {sowing}",
        "irrigation_header": "\n💧 सिंचन मार्गदर्शन:",
        "warning_header": "\n⚠️ इशारे:",
        "source_header": "\n📚 स्रोत:",
        "viability_map": {"good": "चांगली उपयुक्तता", "moderate": "मध्यम उपयुक्तता", "poor": "कमी उपयुक्तता"},
        "deviation_below": "कमी",
        "deviation_above": "जास्त",
    },
    "ta": {
        "header": "🌾 பயிர் ஆலோசனை — {district} மாவட்டம், {season} பருவம்",
        "forecast_warning": "⚠️ எச்சரிக்கை: இந்த பருவத்தில் சராசரியை விட {deviation_abs:.0f}% {deviation_dir} மழை எதிர்பார்க்கப்படுகிறது (கணிப்பு: {projected:.0f} மிமீ, சராசரி: {historical:.0f} மிமீ)",
        "forecast_normal": "✅ இந்த பருவத்தில் சராசரிக்கு நெருக்கமான மழை எதிர்பார்க்கப்படுகிறது (கணிப்பு: {projected:.0f} மிமீ)",
        "crop_header": "\n📋 பயிர் பரிந்துரை:",
        "crop_item": "\n{rank}. {crop} — {viability}\n   காரணம்: {rationale}\n   நீர்: {water_req}\n   விதைப்பு: {sowing}",
        "irrigation_header": "\n💧 நீர்ப்பாசன வழிகாட்டுதல்:",
        "warning_header": "\n⚠️ எச்சரிக்கைகள்:",
        "source_header": "\n📚 ஆதாரங்கள்:",
        "viability_map": {"good": "நல்ல பொருத்தம்", "moderate": "மிதமான பொருத்தம்", "poor": "குறைந்த பொருத்தம்"},
        "deviation_below": "குறைவு",
        "deviation_above": "அதிகம்",
    },
    "en": {
        "header": "🌾 Crop Advisory — {district} District, {season} Season",
        "forecast_warning": "⚠️ Warning: This season's rainfall is projected {deviation_abs:.0f}% {deviation_dir} the historical average (Projected: {projected:.0f}mm, Normal: {historical:.0f}mm)",
        "forecast_normal": "✅ Near-normal rainfall expected this season (Projected: {projected:.0f}mm)",
        "crop_header": "\n📋 Crop Recommendations:",
        "crop_item": "\n{rank}. {crop} — {viability}\n   Rationale: {rationale}\n   Water: {water_req}\n   Sowing: {sowing}",
        "irrigation_header": "\n💧 Irrigation Guidance:",
        "warning_header": "\n⚠️ Warnings:",
        "source_header": "\n📚 Sources:",
        "viability_map": {"good": "Good suitability", "moderate": "Moderate suitability", "poor": "Poor suitability"},
        "deviation_below": "below",
        "deviation_above": "above",
    },
}


def _render_advisory_text(advisory: Advisory, lang: str) -> str:
    """LC-2: Render advisory into localized text from structure."""
    t = TEMPLATES.get(lang, TEMPLATES["en"])

    # Header
    season_names = {"kharif": "Kharif", "rabi": "Rabi", "zaid": "Zaid"}
    text = t["header"].format(
        district=advisory.farmer.district_name,
        season=season_names.get(advisory.forecast.season, advisory.forecast.season),
    )

    # Forecast
    if advisory.forecast.anomaly_flag:
        deviation_dir = t["deviation_below"] if advisory.forecast.deviation_pct < 0 else t["deviation_above"]
        text += "\n\n" + t["forecast_warning"].format(
            deviation_dir=deviation_dir,
            deviation_abs=abs(advisory.forecast.deviation_pct),
            projected=advisory.forecast.projected_rainfall_mm,
            historical=advisory.forecast.historical_mean_mm,
        )
    else:
        text += "\n\n" + t["forecast_normal"].format(
            projected=advisory.forecast.projected_rainfall_mm,
        )

    # Crop recommendations
    if advisory.recommended:
        text += "\n" + t["crop_header"]
        for crop in advisory.recommended:
            viability = t["viability_map"].get(crop.expected_viability.value, crop.expected_viability.value)
            rationale = "; ".join(c.statement for c in crop.rationale)
            water_req = f"{crop.water_requirement_mm:.0f}mm" if crop.water_requirement_mm else "N/A"
            sowing = crop.sowing_window or "N/A"

            text += t["crop_item"].format(
                rank=crop.rank,
                crop=crop.crop,
                viability=viability,
                rationale=rationale[:200],
                water_req=water_req,
                sowing=sowing,
            )

    # Irrigation guidance
    if advisory.irrigation_guidance:
        text += "\n" + t["irrigation_header"]
        for ig in advisory.irrigation_guidance:
            text += f"\n• {ig.statement}"

    # Warnings
    if advisory.warnings:
        text += "\n" + t["warning_header"]
        for w in advisory.warnings:
            text += f"\n• {w}"

    # LC-6: Citation labels
    if advisory.citations:
        text += "\n" + t["source_header"]
        for pid, passage in advisory.citations.items():
            text += f"\n• [{pid}] {passage.doc_title} — {passage.publishing_body} ({passage.year or 'n/a'})"

    return text


def _generate_sms_text(advisory: Advisory, lang: str) -> str:
    """LC-4: Generate SMS text <= 320 chars with the single most decision-relevant fact."""
    if not advisory.recommended:
        return "Seasonal advisory available. Visit Fallow for details. -Fallow"

    top_crop = advisory.recommended[0]
    deviation = advisory.forecast.deviation_pct

    if lang == "hi":
        sms = f"बारिश {deviation:+.0f}%. {top_crop.crop} की सिफारिश."
        if top_crop.sowing_window:
            sms += f" बुवाई: {top_crop.sowing_window}."
        sms += " -फॅलो"
    elif lang == "mr":
        sms = f"पाऊस {deviation:+.0f}%. {top_crop.crop} शिफारस."
        if top_crop.sowing_window:
            sms += f" पेरणी: {top_crop.sowing_window}."
        sms += " -फॅलो"
    elif lang == "ta":
        sms = f"மழை {deviation:+.0f}%. {top_crop.crop} பரிந்துரை."
        if top_crop.sowing_window:
            sms += f" விதைப்பு: {top_crop.sowing_window}."
        sms += " -Fallow"
    else:
        sms = f"Rainfall {deviation:+.0f}%. Recommend: {top_crop.crop}."
        if top_crop.sowing_window:
            sms += f" Sow: {top_crop.sowing_window}."
        sms += " -Fallow"

    # Truncate to 320 chars
    return sms[:320]


async def run_localization_agent(
    advisory: Advisory,
    language: str,
) -> tuple[LocalizedAdvisory, TraceEntry]:
    """
    Execute the Localization Agent.
    
    LC-1: Input is structured Advisory
    LC-2 to LC-6: Template rendering + TTS generation
    """
    start_ms = time.time()
    logger.info(f"Localization Agent: starting for language={language}")

    try:
        # LC-1, LC-2: Render from structured advisory
        full_text = _render_advisory_text(advisory, language)

        # Try to get natural-language phrasing from Granite for non-English
        if language != "en":
            try:
                watsonx = get_watsonx_client()
                natural_prompt = (
                    f"Rewrite the following agricultural advisory in natural, spoken-register "
                    f"{language} language. Keep it conversational and easy to understand for a farmer. "
                    f"Preserve all facts and numbers exactly. Do not add any new information.\n\n"
                    f"Advisory:\n{full_text}\n\n"
                    f"Return ONLY the JSON: {{\"full_text\": \"...\", \"sms_text\": \"...\", \"citation_labels\": {{}}}}"
                )
                response = await watsonx.generate(
                    prompt=natural_prompt,
                    system_prompt="You are a translator. Output valid JSON only.",
                    temperature=0.3,
                )
                try:
                    parsed = json.loads(response.strip().strip("`").strip())
                    if "full_text" in parsed and len(parsed["full_text"]) > 50:
                        full_text = parsed["full_text"]
                except (json.JSONDecodeError, KeyError):
                    pass  # Use template-rendered text
            except Exception as e:
                logger.debug(f"Localization natural phrasing failed, using template: {e}")

        # LC-4: SMS text
        sms_text = _generate_sms_text(advisory, language)

        # LC-5: Generate TTS audio
        # Use a simplified text for TTS (no emojis, no citation IDs)
        tts_text = full_text
        for emoji in ["🌾", "⚠️", "📋", "💧", "📚", "✅"]:
            tts_text = tts_text.replace(emoji, "")
        # Remove citation IDs from TTS text
        import re
        tts_text = re.sub(r'\[P-[a-z0-9]+\]', '', tts_text)
        tts_text = tts_text.strip()

        audio_url = await generate_audio(tts_text, language)

        # LC-6: Citation labels
        citation_labels = {}
        for pid, passage in advisory.citations.items():
            citation_labels[pid] = f"{passage.doc_title} — {passage.publishing_body}"

        localized = LocalizedAdvisory(
            language=language,
            full_text=full_text,
            sms_text=sms_text,
            audio_url=audio_url,
            citation_labels=citation_labels,
        )

        elapsed_ms = int((time.time() - start_ms) * 1000)
        logger.info(f"Localization Agent: completed in {elapsed_ms}ms")

        trace = TraceEntry(
            agent="localization",
            status=AgentStatus.OK,
            ms=elapsed_ms,
            message=f"Advisory localized to {language} with audio",
        )

        return localized, trace

    except Exception as e:
        elapsed_ms = int((time.time() - start_ms) * 1000)
        logger.error(f"Localization Agent: failed after {elapsed_ms}ms — {e}")

        trace = TraceEntry(
            agent="localization",
            status=AgentStatus.ERROR,
            ms=elapsed_ms,
            message=f"Localization failed: {str(e)[:100]}",
        )
        raise

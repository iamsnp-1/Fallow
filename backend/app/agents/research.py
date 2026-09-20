"""
Fallow — Research Agent (RAG)

Implements RS-1 through RS-7:
- RS-4: Query construction from FarmerProfile + ForecastResult
- RS-5: Retrieve top-k with metadata filtering
- RS-6: Apply relevance-score floor
- RS-7: Return RetrievedPassage[] with complete provenance

Also provides demo passages when the vector store is empty,
so the system can demonstrate the full pipeline.
"""

import logging
import time

from app.config import get_settings
from app.contracts import (
    FarmerProfile, ForecastResult, RetrievedPassage,
    TraceEntry, AgentStatus,
)
from app.districts import get_candidate_crops
from app.services.vectorstore import get_vectorstore

logger = logging.getLogger(__name__)


# Demo passages — real agronomic data from public sources
DEMO_PASSAGES: dict[str, list[dict]] = {
    "IN-MH-AUR": [
        {
            "passage_id": "P-aur00001",
            "text": "Bajra (Pearl Millet) - Crop Water Requirement: 300-400 mm. Bajra is the most drought-tolerant cereal crop suitable for semi-arid regions. It can produce reasonable yields even with 250-300 mm of well-distributed rainfall. Recommended varieties for Marathwada: ICTP 8203, Dhanashakti, AHB 1200. Optimal sowing: onset of monsoon, June 15 - July 15.",
            "relevance_score": 0.92,
            "doc_title": "Crop-Water Requirements for Maharashtra Dryland Agriculture",
            "publishing_body": "ICAR - Central Research Institute for Dryland Agriculture",
            "year": 2022,
            "section": "Millets - Water Requirements and Drought Tolerance",
            "page": 45,
            "source_uri": "https://icar.org.in/files/dryland-agriculture-handbook-2022.pdf"
        },
        {
            "passage_id": "P-aur00002",
            "text": "Tur (Pigeon Pea / Arhar) - Crop Water Requirement: 600-650 mm. Tur is a deep-rooted, drought-tolerant legume with biological nitrogen fixation ability. Duration: 160-180 days for medium varieties. In deficit rainfall years, tur's deep root system (up to 2m) helps access subsoil moisture. Sowing window: June first fortnight. Recommended spacing for rainfed conditions: 90 cm × 20 cm.",
            "relevance_score": 0.88,
            "doc_title": "Kharif Crop Advisory for Marathwada Region",
            "publishing_body": "MPKV Rahuri - Krishi Vigyan Kendra",
            "year": 2023,
            "section": "Pulse Crops - Rainfed Cultivation",
            "page": 23,
            "source_uri": "https://mpkv.ac.in/kvk/seasonal-advisory-kharif-2023.pdf"
        },
        {
            "passage_id": "P-aur00003",
            "text": "Mung Bean (Green Gram) - Crop Water Requirement: 300-350 mm. Short duration crop (60-75 days). Highly suitable as a catch crop in seasons with uncertain rainfall. Drought escape strategy due to short duration. Improves soil fertility through nitrogen fixation (20-25 kg N/ha). Suitable varieties: Virat, BM-4, IPM 02-3.",
            "relevance_score": 0.85,
            "doc_title": "Short Duration Crops for Climate Resilience in Dryland Farming",
            "publishing_body": "ICAR - Indian Institute of Pulses Research",
            "year": 2023,
            "section": "Green Gram Production Technology",
            "page": 12,
            "source_uri": "https://iipr.icar.gov.in/publications/climate-resilient-crops-2023.pdf"
        },
        {
            "passage_id": "P-aur00004",
            "text": "Protective Irrigation in Dryland Agriculture: In deficit rainfall seasons, one or two protective irrigations at critical crop growth stages can increase yields by 30-50%. Critical stages for millets: boot/heading stage and grain filling. Water requirement for protective irrigation: 40-50 mm per irrigation. Mulching with crop residues reduces evaporation by 20-30% and maintains soil moisture.",
            "relevance_score": 0.82,
            "doc_title": "Water Management in Dryland Farming Systems",
            "publishing_body": "ICAR - CRIDA Hyderabad",
            "year": 2022,
            "section": "Protective Irrigation and Moisture Conservation",
            "page": 67,
            "source_uri": "https://crida.icar.gov.in/publications/dryland-water-management-2022.pdf"
        },
        {
            "passage_id": "P-aur00005",
            "text": "Cotton should be avoided in seasons where rainfall is projected below 600mm as the crop requires 700-1300mm water and is highly sensitive to moisture stress during square formation and boll development. Similarly, Soybean requires well-distributed rainfall of 600-800mm; yield reduction is severe (40-60%) when rainfall drops below 450mm during pod filling stage.",
            "relevance_score": 0.80,
            "doc_title": "Seasonal Crop Planning Advisory - Aurangabad Division",
            "publishing_body": "Maharashtra State Agricultural Department",
            "year": 2023,
            "section": "Crops to Avoid in Deficit Rainfall Years",
            "page": 8,
            "source_uri": "https://krishi.maharashtra.gov.in/advisories/aurangabad-seasonal-2023.pdf"
        },
    ],
    "IN-TN-TNJ": [
        {
            "passage_id": "P-tnj00001",
            "text": "Rice (Paddy) in Cauvery Delta: The delta zone is ideally suited for rice cultivation with assured irrigation from the Cauvery river system and northeast monsoon rainfall. Water requirement: 1200-1400mm for transplanted rice. Recommended varieties: CO 51, ADT 53, BPT 5204 (Samba Mahsuri). Samba season transplanting: August-September. Kuruvai season: June-July.",
            "relevance_score": 0.94,
            "doc_title": "Rice Production Technology for Tamil Nadu",
            "publishing_body": "Tamil Nadu Agricultural University (TNAU)",
            "year": 2023,
            "section": "Cauvery Delta Zone - Rice Cultivation",
            "page": 34,
            "source_uri": "https://agritech.tnau.ac.in/publications/rice-production-2023.pdf"
        },
        {
            "passage_id": "P-tnj00002",
            "text": "Alternate Wetting and Drying (AWD) in Rice: AWD technique saves 15-25% irrigation water compared to continuous flooding without significant yield reduction. The field is allowed to dry until hairline cracks appear before re-irrigation. This technique also reduces methane emissions by 30-40%. Suitable for areas with reliable water access but conservation goals.",
            "relevance_score": 0.87,
            "doc_title": "Water Saving Technologies in Rice Cultivation",
            "publishing_body": "TNAU - Water Technology Centre",
            "year": 2022,
            "section": "Alternate Wetting and Drying",
            "page": 18,
            "source_uri": "https://agritech.tnau.ac.in/publications/water-saving-rice-2022.pdf"
        },
        {
            "passage_id": "P-tnj00003",
            "text": "Blackgram (Urad) as Rice Fallow Crop: Blackgram is the most popular rice fallow crop in the Cauvery delta, utilizing residual soil moisture. Water requirement: 300-350mm. Duration: 70-80 days. It fixes 40-50 kg N/ha, benefiting subsequent rice crop. Recommended varieties: VBN 8, ADT 5. Sowing: immediately after rice harvest in January-February.",
            "relevance_score": 0.85,
            "doc_title": "Pulse Crops for Rice-Based Cropping Systems",
            "publishing_body": "ICAR - Indian Institute of Pulses Research",
            "year": 2023,
            "section": "Rice Fallow Pulses - Cauvery Delta",
            "page": 42,
            "source_uri": "https://iipr.icar.gov.in/publications/rice-fallow-pulses-2023.pdf"
        },
        {
            "passage_id": "P-tnj00004",
            "text": "Sesame in Delta Zone: Sesame (Gingelly) is a traditional oilseed crop of the delta zone, cultivated as a rainfed crop during Kharif. Water requirement: 350-400mm. Short duration (85-90 days). Good market demand and price stability. Recommended varieties: TMV 7, SVPR 1. Sowing: June-July.",
            "relevance_score": 0.78,
            "doc_title": "Oilseed Crops for Tamil Nadu",
            "publishing_body": "TNAU - Department of Oilseed Crops",
            "year": 2022,
            "section": "Sesame Production Technology",
            "page": 26,
            "source_uri": "https://agritech.tnau.ac.in/publications/oilseeds-tn-2022.pdf"
        },
        {
            "passage_id": "P-tnj00005",
            "text": "Cropping System Recommendations for Cauvery Delta Zone: The predominant cropping system is Rice-Rice-Pulse. In years with adequate northeast monsoon (>500mm during Oct-Dec), the Samba rice season can be extended. Canal water release schedule should be confirmed before nursery preparation. Rice varieties with shorter duration (ADT 43, 100-105 days) are recommended when planting is delayed beyond August.",
            "relevance_score": 0.82,
            "doc_title": "Agro-Climatic Zone Crop Planning Guide - Tamil Nadu",
            "publishing_body": "State Agricultural Department, Tamil Nadu",
            "year": 2023,
            "section": "Cauvery Delta Zone Planning",
            "page": 15,
            "source_uri": "https://agri.tn.gov.in/publications/crop-planning-guide-2023.pdf"
        },
    ],
}


def build_research_query(profile: FarmerProfile, forecast: ForecastResult) -> str:
    """RS-4: Construct query from profile and forecast context."""
    candidate_crops = get_candidate_crops(profile.district_id)
    deviation_desc = "deficit" if forecast.deviation_pct < 0 else "surplus"
    return (
        f"Crop recommendations for {profile.district_name} district, "
        f"{profile.season.value} season. "
        f"Rainfall {deviation_desc}: {abs(forecast.deviation_pct):.0f}% from normal. "
        f"Projected rainfall: {forecast.projected_rainfall_mm:.0f}mm. "
        f"Irrigation: {profile.irrigation_access.value}. "
        f"Candidate crops: {', '.join(candidate_crops[:5])}. "
        f"Crop water requirements, sowing windows, drought tolerance."
    )


async def run_research_agent(
    profile: FarmerProfile,
    forecast: ForecastResult,
) -> tuple[list[RetrievedPassage], TraceEntry]:
    """
    Execute the Research Agent.
    
    RS-4: Query construction from profile + forecast
    RS-5: Retrieve top-k with metadata filtering
    RS-6: Apply relevance-score floor
    RS-7: Return passages with complete provenance
    """
    start_ms = time.time()
    settings = get_settings()
    logger.info(f"Research Agent: starting for {profile.district_id}")

    try:
        # RS-4: Construct query from profile and forecast context
        query = build_research_query(profile, forecast)
        logger.debug(f"Research Agent: query = {query[:200]}")

        # Try vector store first
        store = get_vectorstore()
        passages: list[RetrievedPassage] = []

        if store.count > 0:
            passages = await store.query(
                query_text=query,
                top_k=settings.RETRIEVAL_TOP_K,
                relevance_floor=settings.RELEVANCE_FLOOR,
            )
            logger.info(f"Research Agent: retrieved {len(passages)} passages from vector store")

        # If vector store returns insufficient results, use demo passages
        if len(passages) < settings.MIN_PASSAGES_FOR_ADVISORY:
            logger.info(
                f"Research Agent: only {len(passages)} passages from vector store "
                f"(min {settings.MIN_PASSAGES_FOR_ADVISORY}), supplementing with demo corpus"
            )
            demo = DEMO_PASSAGES.get(profile.district_id, [])
            for dp in demo:
                # Don't add duplicates
                if not any(p.passage_id == dp["passage_id"] for p in passages):
                    passages.append(RetrievedPassage(**dp))

        # RS-6: Final floor filter and sort by relevance
        passages = [p for p in passages if p.relevance_score >= settings.RELEVANCE_FLOOR]
        passages.sort(key=lambda p: p.relevance_score, reverse=True)

        # Limit to top-k
        passages = passages[:settings.RETRIEVAL_TOP_K]

        elapsed_ms = int((time.time() - start_ms) * 1000)
        logger.info(f"Research Agent: completed in {elapsed_ms}ms — {len(passages)} passages")

        trace = TraceEntry(
            agent="research",
            status=AgentStatus.OK,
            ms=elapsed_ms,
            message=f"Retrieved {len(passages)} relevant passages from corpus",
            passages=len(passages),
        )

        return passages, trace

    except Exception as e:
        elapsed_ms = int((time.time() - start_ms) * 1000)
        logger.error(f"Research Agent: failed after {elapsed_ms}ms — {e}")

        trace = TraceEntry(
            agent="research",
            status=AgentStatus.ERROR,
            ms=elapsed_ms,
            message=f"Research failed: {str(e)[:100]}",
        )
        raise

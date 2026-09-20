"""
Utility to generate authenticated sample agronomic PDFs in data/corpus
for testing PyMuPDF parsing and ChromaDB ingestion.
"""

from pathlib import Path
import fitz  # PyMuPDF

CORPUS_DIR = Path("./backend/data/corpus")
CORPUS_DIR.mkdir(parents=True, exist_ok=True)

AUR_CONTENT = """# ICAR - Central Research Institute for Dryland Agriculture
Crop-Water Requirements and Contingency Planning for Semi-Arid Tropics (2022)

## 1. Agro-Climatic Zone Context: Marathwada & Western Scarcity Zone
The scarcity zone of Maharashtra receives an average annual rainfall between 500-750 mm. In drought or deficit monsoon years, dryland crops require specific conservation techniques.

## 2. Millets - Water Requirements and Drought Tolerance
Bajra (Pearl Millet) requires 300-400 mm of water throughout its growing period of 75-85 days. It is the premier climate-resilient cereal crop for light to medium black soils under deficit conditions. Recommended varieties include ICTP 8203, Dhanashakti (biofortified), and AHB 1200. Sowing should occur within 15 days of monsoon arrival.

## 3. Pulse Crops - Rainfed Cultivation & Nitrogen Fixation
Tur (Pigeon Pea / Arhar) has a deep taproot system penetrating up to 2 meters, enabling access to deep subsoil moisture reserves. It requires 600-650 mm over 150-170 days and fixes up to 40 kg atmospheric nitrogen per hectare. Intercropping bajra + tur in a 2:1 or 3:1 ratio provides risk diversification against mid-season dry spells.

Mung Bean (Green Gram) requires only 300-350 mm of water with a short maturity window of 60-75 days. It acts as an effective catch crop and minimizes economic exposure during erratic rainfall onset. Recommended varieties include BM-4 and Virat.

## 4. Soil Moisture Conservation & Protective Irrigation
Under severe rainfall deficit (>20% below normal), farmers should apply straw mulching at 5 tonnes per hectare to suppress evaporative moisture loss. Protective irrigation must be prioritized during flowering and pod development stages.
"""

TNJ_CONTENT = """# Tamil Nadu Agricultural University (TNAU)
Cauvery Delta Zone Crop Planning & Water Management Guide (2023)

## 1. Agro-Climatic Zone Profile: Cauvery Delta
The Cauvery Delta Zone enjoys alluvial fertile soils with canal irrigation networks and receives rainfall from both Southwest and Northeast monsoons (annual mean: 900-1100 mm). Rice is the foundation crop of this delta ecosystem.

## 2. Cauvery Delta Zone - Rice Cultivation
Transplanted wetland rice requires 1200-1400 mm of water throughout its crop growth cycle. For the Kuruvai season (June-July), short-duration varieties like ADT 43 and CO 51 are recommended. For the Samba season (August-January), medium-duration varieties such as CR 1009 Sub-1 and BPT 5204 (Samba Mahsuri) perform reliably with assured irrigation.

## 3. Water Saving Technologies in Rice Cultivation
Alternate Wetting and Drying (AWD) irrigation methodology saves 15-25% water without reducing grain yield. A perforated field water tube is inserted 15 cm into the soil to monitor water depth. Re-irrigation is applied when water recedes to 15 cm below ground surface.

## 4. Rice Fallow Pulses - Cauvery Delta
Blackgram (Urad bean) and Greengram are ideal rice-fallow relay crops sown 4-6 days prior to rice harvest directly into residual moisture. Water requirement is minimal (300-350 mm). Blackgram fixes 45 kg N/ha, replenishing soil organic fertility. Recommended varieties include VBN 8, VBN 9, and ADT 5.

Sesame (Gingelly) is cultivated extensively as a summer rice-fallow or Kharif semi-dry crop, requiring 350-400 mm with high market demand and economic returns.
"""

def create_pdf(filename: str, text: str):
    doc = fitz.open()
    # Split by double newline into pages/paragraphs
    paragraphs = text.strip().split("\n\n")
    page = doc.new_page()
    p_rect = fitz.Rect(50, 50, 550, 750)
    
    y = 60
    for p in paragraphs:
        if p.startswith("# "):
            page.insert_text((50, y), p.replace("# ", ""), fontsize=16, fontname="helv", color=(0.1, 0.2, 0.4))
            y += 28
        elif p.startswith("## "):
            page.insert_text((50, y), p.replace("## ", ""), fontsize=12, fontname="helv", color=(0.15, 0.35, 0.2))
            y += 20
        else:
            # Wrap regular text
            rect = fitz.Rect(50, y, 540, y + 100)
            page.insert_textbox(rect, p, fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
            y += 75
        
        if y > 700:
            page = doc.new_page()
            y = 60

    filepath = CORPUS_DIR / filename
    doc.save(str(filepath))
    doc.close()
    print(f"Created PDF: {filepath}")

if __name__ == "__main__":
    create_pdf("ICAR_Dryland_Agriculture_Handbook_2022.pdf", AUR_CONTENT)
    create_pdf("TNAU_Cauvery_Delta_Rice_and_Pulses_2023.pdf", TNJ_CONTENT)

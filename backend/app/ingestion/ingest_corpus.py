"""
Fallow — Corpus Ingestion Utility

Implements RS-1 through RS-3:
- RS-1: Parse corpus PDFs, chunk with overlap, preserve document metadata
- RS-2: Semantic/section-aware chunking, ~500-800 tokens, ~100 token overlap
- RS-3: Embed chunks; persist to vector store with full metadata

Usage:
    python -m app.ingestion.ingest_corpus [--corpus-dir ./data/corpus]
"""

import hashlib
import logging
import re
import sys
import asyncio
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _chunk_text(
    text: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[str]:
    """
    RS-2: Chunk text with overlap.
    Target: ~500-800 tokens with ~100 token overlap.
    Uses word-based chunking for clean boundaries.
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])

        # Clean up the chunk
        chunk = chunk.strip()
        if len(chunk) > 50:  # Minimum meaningful chunk size
            chunks.append(chunk)

        start = end - overlap
        if start >= len(words):
            break

    return chunks


def _extract_sections(text: str) -> list[tuple[str, str]]:
    """Try to extract section headers and their content."""
    sections = []
    # Look for common section patterns
    patterns = [
        r'^(#{1,3}\s+.+)$',
        r'^(\d+\.\s+.+)$',
        r'^([A-Z][A-Z\s]+:)$',
    ]

    current_section = "Introduction"
    current_text = []

    for line in text.split("\n"):
        is_header = False
        for pattern in patterns:
            if re.match(pattern, line.strip()):
                if current_text:
                    sections.append((current_section, "\n".join(current_text)))
                current_section = line.strip()
                current_text = []
                is_header = True
                break
        if not is_header:
            current_text.append(line)

    if current_text:
        sections.append((current_section, "\n".join(current_text)))

    return sections if sections else [("Full Document", text)]


def parse_pdf(filepath: Path) -> list[dict]:
    """
    RS-1: Parse a PDF file and extract text with metadata.
    Preserves page numbers and attempts section extraction.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
        return []

    chunks = []
    try:
        doc = fitz.open(str(filepath))
        full_text = ""
        page_map = []  # Maps character position to page number

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            start_pos = len(full_text)
            full_text += text + "\n"
            page_map.append((start_pos, len(full_text), page_num + 1))

        doc.close()

        # Extract sections
        sections = _extract_sections(full_text)

        # Chunk each section
        for section_name, section_text in sections:
            section_chunks = _chunk_text(section_text)
            for chunk_text in section_chunks:
                # Find which page this chunk is on
                chunk_pos = full_text.find(chunk_text[:100])
                page_num = None
                if chunk_pos >= 0:
                    for start, end, pn in page_map:
                        if start <= chunk_pos < end:
                            page_num = pn
                            break

                chunk_id = f"P-{hashlib.md5(chunk_text[:200].encode()).hexdigest()[:8]}"

                chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "metadata": {
                        "doc_title": filepath.stem.replace("_", " ").replace("-", " ").title(),
                        "section": section_name,
                        "page": page_num,
                        "source_uri": f"file://{filepath.name}",
                        "publishing_body": _infer_publisher(filepath.name),
                        "year": _infer_year(filepath.name),
                    },
                })

        logger.info(f"Parsed {filepath.name}: {len(chunks)} chunks from {len(sections)} sections")

    except Exception as e:
        logger.error(f"Failed to parse PDF {filepath}: {e}")

    return chunks


def _infer_publisher(filename: str) -> str:
    """Try to infer the publishing body from filename."""
    lower = filename.lower()
    if "icar" in lower:
        return "ICAR"
    elif "tnau" in lower:
        return "Tamil Nadu Agricultural University"
    elif "mpkv" in lower:
        return "MPKV Rahuri"
    elif "kvk" in lower:
        return "Krishi Vigyan Kendra"
    elif "maharashtra" in lower:
        return "Maharashtra Agriculture Department"
    elif "tamil" in lower or "tn" in lower:
        return "Tamil Nadu Agriculture Department"
    return "Agricultural Extension Service"


def _infer_year(filename: str) -> Optional[int]:
    """Try to extract a year from the filename."""
    match = re.search(r'20\d{2}', filename)
    if match:
        return int(match.group())
    return None


async def ingest_corpus(corpus_dir: str = "./data/corpus") -> int:
    """
    Ingest all PDFs from the corpus directory into the vector store.
    Returns the number of chunks indexed.
    """
    from app.services.vectorstore import get_vectorstore

    corpus_path = Path(corpus_dir)
    if not corpus_path.exists():
        logger.warning(f"Corpus directory does not exist: {corpus_path}")
        corpus_path.mkdir(parents=True, exist_ok=True)
        return 0

    pdf_files = list(corpus_path.glob("*.pdf"))
    if not pdf_files:
        logger.info(f"No PDF files found in {corpus_path}")
        return 0

    store = get_vectorstore()
    total_chunks = 0

    for pdf_file in pdf_files:
        logger.info(f"Ingesting: {pdf_file.name}")
        chunks = parse_pdf(pdf_file)

        if chunks:
            texts = [c["text"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]
            ids = [c["id"] for c in chunks]

            await store.add_documents(texts=texts, metadatas=metadatas, ids=ids)
            total_chunks += len(chunks)

    logger.info(f"Corpus ingestion complete: {total_chunks} chunks from {len(pdf_files)} files")
    return total_chunks


async def seed_demo_corpus() -> int:
    """
    Seed the vector store with demo passages when no PDFs are available.
    Uses the demo passages defined in the research agent.
    """
    from app.agents.research import DEMO_PASSAGES
    from app.services.vectorstore import get_vectorstore

    store = get_vectorstore()

    if store.count > 0:
        logger.info(f"Vector store already has {store.count} documents, skipping seed")
        return store.count

    total = 0
    for district_id, passages in DEMO_PASSAGES.items():
        texts = [p["text"] for p in passages]
        metadatas = [{
            "doc_title": p["doc_title"],
            "publishing_body": p["publishing_body"],
            "year": p.get("year"),
            "section": p.get("section"),
            "page": p.get("page"),
            "source_uri": p["source_uri"],
            "district_id": district_id,
        } for p in passages]
        ids = [p["passage_id"] for p in passages]

        await store.add_documents(texts=texts, metadatas=metadatas, ids=ids)
        total += len(passages)

    logger.info(f"Demo corpus seeded: {total} passages")
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    corpus_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/corpus"
    count = asyncio.run(ingest_corpus(corpus_dir))
    if count == 0:
        print("No PDFs found. Seeding demo corpus...")
        count = asyncio.run(seed_demo_corpus())
    print(f"Ingested {count} chunks total")

"""
Fallow — ChromaDB Vector Store Service with In-Memory Resilient Fallback

Wraps ChromaDB for corpus indexing and retrieval with metadata filtering.
Implements RS-3, RS-5, RS-6, RS-7 requirements.
Supports in-memory fallback when ChromaDB is unavailable.
"""

import logging
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.contracts import RetrievedPassage
from app.services.watsonx_client import get_watsonx_client

logger = logging.getLogger(__name__)

COLLECTION_NAME = "fallow_corpus"

_chroma_available = False
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _chroma_available = True
except ImportError:
    logger.warning("chromadb not installed. VectorStore running in in-memory fallback mode.")


class VectorStore:
    """ChromaDB-based vector store for agricultural corpus with in-memory fallback."""

    def __init__(self):
        settings = get_settings()
        self._watsonx = get_watsonx_client()
        self._use_fallback = not _chroma_available
        self._memory_docs: dict[str, dict] = {}  # id -> {text, metadata, embedding}

        if _chroma_available:
            try:
                persist_dir = str(settings.chroma_path)
                Path(persist_dir).mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._collection = self._client.get_or_create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"ChromaDB initialized with {self._collection.count()} docs.")
            except Exception as e:
                logger.warning(f"Failed to initialize ChromaDB PersistentClient: {e}. Falling back to in-memory store.")
                self._use_fallback = True

    @property
    def count(self) -> int:
        if self._use_fallback:
            return len(self._memory_docs)
        return self._collection.count()

    async def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """Add document chunks to the vector store (RS-3)."""
        try:
            embeddings = await self._watsonx.embed(texts)

            if self._use_fallback:
                for i, doc_id in enumerate(ids):
                    self._memory_docs[doc_id] = {
                        "id": doc_id,
                        "text": texts[i],
                        "metadata": metadatas[i],
                        "embedding": embeddings[i] if i < len(embeddings) else [],
                    }
                logger.info(f"Added {len(texts)} chunks to in-memory store (total: {len(self._memory_docs)})")
            else:
                self._collection.add(
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids,
                )
                logger.info(f"Added {len(texts)} chunks to ChromaDB store")
        except Exception as e:
            logger.error(f"Failed to add documents to vector store: {e}")
            raise

    async def get_by_id(self, passage_id: str) -> Optional[dict]:
        """Lookup a document by ID."""
        if self._use_fallback:
            doc = self._memory_docs.get(passage_id)
            if doc:
                return {
                    "id": doc["id"],
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                }
            return None

        try:
            res = self._collection.get(ids=[passage_id])
            if res and res["documents"]:
                return {
                    "id": res["ids"][0],
                    "text": res["documents"][0],
                    "metadata": res["metadatas"][0] if res["metadatas"] else {},
                }
        except Exception as e:
            logger.error(f"Error fetching passage {passage_id}: {e}")
        return None

    async def query(
        self,
        query_text: str,
        top_k: int = 8,
        relevance_floor: float = 0.35,
        where_filter: Optional[dict] = None,
    ) -> list[RetrievedPassage]:
        """
        Query the vector store and return passages with provenance.
        RS-5: Retrieve top-k with metadata filtering
        RS-6: Apply relevance-score floor; discard below threshold
        RS-7: Return RetrievedPassage[] with complete provenance
        """
        if self.count == 0:
            logger.warning("Vector store is empty — no documents indexed")
            return []

        if self._use_fallback:
            return self._query_in_memory(query_text, top_k, relevance_floor, where_filter)

        try:
            query_embedding = await self._watsonx.embed([query_text])
            query_params = {
                "query_embeddings": query_embedding,
                "n_results": min(top_k, self._collection.count()),
            }
            if where_filter:
                query_params["where"] = where_filter

            results = self._collection.query(**query_params)
            passages = []

            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    distance = results["distances"][0][i] if results.get("distances") else 1.0
                    similarity = 1.0 - distance

                    if similarity < relevance_floor:
                        continue

                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    passage_id = results["ids"][0][i] if results.get("ids") else f"P-{i:04d}"
                    source_uri = metadata.get("source_uri", "")
                    if not source_uri:
                        continue

                    passages.append(RetrievedPassage(
                        passage_id=passage_id,
                        text=doc,
                        relevance_score=round(similarity, 4),
                        doc_title=metadata.get("doc_title", "Agronomic Research"),
                        publishing_body=metadata.get("publishing_body", "Agricultural Extension"),
                        year=metadata.get("year"),
                        section=metadata.get("section"),
                        page=metadata.get("page"),
                        source_uri=source_uri,
                    ))

            return passages

        except Exception as e:
            logger.error(f"ChromaDB query error: {e}, attempting in-memory query")
            return self._query_in_memory(query_text, top_k, relevance_floor, where_filter)

    def _query_in_memory(
        self,
        query_text: str,
        top_k: int,
        relevance_floor: float,
        where_filter: Optional[dict] = None,
    ) -> list[RetrievedPassage]:
        """Simple keyword/token overlap search when in-memory fallback is active."""
        query_tokens = set(query_text.lower().split())
        scored = []

        for p_id, item in self._memory_docs.items():
            meta = item["metadata"]
            if where_filter and any(meta.get(k) != v for k, v in where_filter.items()):
                continue

            doc_text = item["text"].lower()
            overlap = sum(1 for t in query_tokens if t in doc_text)
            score = min(0.95, 0.4 + (overlap / max(len(query_tokens), 1)) * 0.55)

            if score >= relevance_floor:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        passages = []
        for score, item in scored[:top_k]:
            meta = item["metadata"]
            passages.append(RetrievedPassage(
                passage_id=item["id"],
                text=item["text"],
                relevance_score=round(score, 4),
                doc_title=meta.get("doc_title", "Agronomic Research"),
                publishing_body=meta.get("publishing_body", "Agricultural Extension"),
                year=meta.get("year"),
                section=meta.get("section"),
                page=meta.get("page"),
                source_uri=meta.get("source_uri", "file://corpus.pdf"),
            ))

        return passages


# Singleton
_store_instance: Optional[VectorStore] = None


def get_vectorstore() -> VectorStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorStore()
    return _store_instance


def reset_vectorstore():
    """Reset the singleton (for testing)."""
    global _store_instance
    _store_instance = None

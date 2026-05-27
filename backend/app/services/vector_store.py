"""Vector store abstraction backed by Pinecone, with an in-memory fallback."""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, List, Optional, Protocol

from app.core.config import get_settings
from app.services.hybrid_search import (
    DEFAULT_ALPHA,
    SparseVector,
    combine_dense_sparse,
    scale_sparse_vector,
    sparse_dot,
)

PINECONE_UPSERT_BATCH = 100
PINECONE_FREE_TIER_LIMIT = 100_000


@dataclass
class VectorMatch:
    id: str
    score: float
    metadata: Dict[str, Any]
    dense_score: float | None = None
    sparse_score: float = 0.0


@dataclass
class VectorRecord:
    id: str
    values: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    sparse_values: SparseVector | None = None


class VectorStore(Protocol):
    async def upsert(self, records: List[VectorRecord]) -> None: ...

    async def query(
        self,
        vector: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        sparse_vector: SparseVector | None = None,
        alpha: float = DEFAULT_ALPHA,
    ) -> List[VectorMatch]: ...

    async def delete(self, ids: List[str]) -> None: ...

    async def count(self) -> int: ...


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _batch(items: List[VectorRecord], size: int) -> List[List[VectorRecord]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class InMemoryVectorStore:
    """Simple cosine-similarity store used when Pinecone isn't configured."""

    def __init__(self) -> None:
        self._records: Dict[str, VectorRecord] = {}
        self._lock = RLock()

    async def upsert(self, records: List[VectorRecord]) -> None:
        with self._lock:
            for record in records:
                self._records[record.id] = record

    async def query(
        self,
        vector: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        sparse_vector: SparseVector | None = None,
        alpha: float = DEFAULT_ALPHA,
    ) -> List[VectorMatch]:
        with self._lock:
            candidates = list(self._records.values())

        if document_ids:
            allowed = set(document_ids)
            candidates = [r for r in candidates if r.metadata.get("document_id") in allowed]

        scored: list[VectorMatch] = []
        for record in candidates:
            dense_score = _cosine(vector, record.values)
            sparse_score = sparse_dot(sparse_vector, record.sparse_values)
            score = (
                combine_dense_sparse(dense_score, sparse_score, alpha=alpha)
                if sparse_vector
                else dense_score
            )
            scored.append(
                VectorMatch(
                    id=record.id,
                    score=score,
                    metadata=record.metadata,
                    dense_score=dense_score,
                    sparse_score=sparse_score,
                )
            )
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

    async def delete(self, ids: List[str]) -> None:
        with self._lock:
            for vec_id in ids:
                self._records.pop(vec_id, None)

    async def count(self) -> int:
        with self._lock:
            return len(self._records)


class PineconeVectorStore:
    """Pinecone-backed vector store using the serverless `medquery` index."""

    def __init__(
        self,
        api_key: str,
        index_name: str,
        cloud: str,
        region: str,
        dimension: int,
        metric: str,
    ) -> None:
        from pinecone import Pinecone, ServerlessSpec

        self._pc = Pinecone(api_key=api_key)
        existing = {idx["name"] for idx in self._pc.list_indexes()}
        if index_name not in existing:
            self._pc.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec=ServerlessSpec(cloud=cloud, region=region),
            )
        self._index = self._pc.Index(index_name)

    async def upsert(self, records: List[VectorRecord]) -> None:
        if not records:
            return
        # Pinecone caps each upsert request at 100 vectors.
        for batch in _batch(records, PINECONE_UPSERT_BATCH):
            payload = [
                {
                    "id": r.id,
                    "values": r.values,
                    "metadata": r.metadata,
                    **({"sparse_values": r.sparse_values} if r.sparse_values else {}),
                }
                for r in batch
            ]
            await asyncio.to_thread(self._index.upsert, vectors=payload)

    async def query(
        self,
        vector: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        sparse_vector: SparseVector | None = None,
        alpha: float = DEFAULT_ALPHA,
    ) -> List[VectorMatch]:
        filter_: Dict[str, Any] | None = None
        if document_ids:
            filter_ = {"document_id": {"$in": list(document_ids)}}

        query_kwargs: Dict[str, Any] = {
            "vector": [value * alpha for value in vector] if sparse_vector else vector,
            "top_k": top_k,
            "include_metadata": True,
            "filter": filter_,
        }
        if sparse_vector:
            query_kwargs["sparse_vector"] = scale_sparse_vector(sparse_vector, 1.0 - alpha)

        try:
            response = await asyncio.to_thread(self._index.query, **query_kwargs)
        except Exception:
            # Existing cosine-only indexes cannot accept sparse query payloads.
            # Fall back to dense retrieval rather than failing the clinical query.
            query_kwargs.pop("sparse_vector", None)
            response = await asyncio.to_thread(self._index.query, **query_kwargs)
        return [
            VectorMatch(id=m["id"], score=float(m["score"]), metadata=m.get("metadata") or {})
            for m in response.get("matches", [])
        ]

    async def delete(self, ids: List[str]) -> None:
        if not ids:
            return
        # Pinecone delete by id also limits batch sizes; chunk to be safe.
        for i in range(0, len(ids), PINECONE_UPSERT_BATCH):
            batch = ids[i : i + PINECONE_UPSERT_BATCH]
            await asyncio.to_thread(self._index.delete, ids=batch)

    async def count(self) -> int:
        try:
            stats = await asyncio.to_thread(self._index.describe_index_stats)
            return int(stats.get("total_vector_count", 0))
        except Exception:
            return 0


_singleton_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _singleton_store
    if _singleton_store is not None:
        return _singleton_store

    settings = get_settings()
    if settings.use_fake_providers or not settings.pinecone_api_key:
        _singleton_store = InMemoryVectorStore()
    else:
        from app.services.embeddings import EMBEDDING_DIM

        _singleton_store = PineconeVectorStore(
            api_key=settings.pinecone_api_key,
            index_name=settings.pinecone_index,
            cloud=settings.pinecone_cloud,
            region=settings.pinecone_region,
            dimension=EMBEDDING_DIM,
            metric=settings.pinecone_metric,
        )
    return _singleton_store


def reset_vector_store() -> None:
    """Test helper: drop the singleton instance."""
    global _singleton_store
    _singleton_store = None

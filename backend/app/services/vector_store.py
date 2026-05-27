"""Vector store abstraction backed by Pinecone, with an in-memory fallback."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, List, Optional, Protocol

from app.core.config import get_settings


@dataclass
class VectorMatch:
    id: str
    score: float
    metadata: Dict[str, Any]


@dataclass
class VectorRecord:
    id: str
    values: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorStore(Protocol):
    async def upsert(self, records: List[VectorRecord]) -> None: ...

    async def query(
        self,
        vector: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> List[VectorMatch]: ...

    async def delete(self, ids: List[str]) -> None: ...


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


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
    ) -> List[VectorMatch]:
        with self._lock:
            candidates = list(self._records.values())

        if document_ids:
            allowed = set(document_ids)
            candidates = [r for r in candidates if r.metadata.get("document_id") in allowed]

        scored = [
            VectorMatch(id=r.id, score=_cosine(vector, r.values), metadata=r.metadata)
            for r in candidates
        ]
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

    async def delete(self, ids: List[str]) -> None:
        with self._lock:
            for vec_id in ids:
                self._records.pop(vec_id, None)


class PineconeVectorStore:
    """Pinecone-backed vector store using the serverless `medquery` index."""

    def __init__(self, api_key: str, index_name: str, cloud: str, region: str, dimension: int) -> None:
        from pinecone import Pinecone, ServerlessSpec

        self._pc = Pinecone(api_key=api_key)
        existing = {idx["name"] for idx in self._pc.list_indexes()}
        if index_name not in existing:
            self._pc.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=cloud, region=region),
            )
        self._index = self._pc.Index(index_name)

    async def upsert(self, records: List[VectorRecord]) -> None:
        import asyncio

        payload = [
            {"id": r.id, "values": r.values, "metadata": r.metadata} for r in records
        ]
        await asyncio.to_thread(self._index.upsert, vectors=payload)

    async def query(
        self,
        vector: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> List[VectorMatch]:
        import asyncio

        filter_: Dict[str, Any] | None = None
        if document_ids:
            filter_ = {"document_id": {"$in": list(document_ids)}}

        response = await asyncio.to_thread(
            self._index.query,
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter_,
        )
        return [
            VectorMatch(id=m["id"], score=float(m["score"]), metadata=m.get("metadata") or {})
            for m in response.get("matches", [])
        ]

    async def delete(self, ids: List[str]) -> None:
        import asyncio

        if not ids:
            return
        await asyncio.to_thread(self._index.delete, ids=ids)


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
        )
    return _singleton_store


def reset_vector_store() -> None:
    """Test helper: drop the singleton instance."""
    global _singleton_store
    _singleton_store = None

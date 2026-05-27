"""Document ingestion pipeline shared by API endpoints and background workers."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from sqlalchemy import delete as sa_delete

from app.db.session import AsyncSessionLocal
from app.models.document import Document
from app.models.entity import Entity
from app.services.embeddings import get_embedding_provider
from app.services.entity_extraction import extract_entities
from app.services.hybrid_search import build_sparse_vector, sparse_keywords
from app.services.redaction import redact_chunks
from app.services.text_extraction import extract_text, split_chunks
from app.services.vector_store import (
    PINECONE_FREE_TIER_LIMIT,
    VectorRecord,
    get_vector_store,
)

logger = logging.getLogger(__name__)
PINECONE_WARN_RATIO = 0.9


@dataclass
class IngestResult:
    document_id: str
    status: str
    chunk_count: int = 0
    pinecone_ids: List[str] = field(default_factory=list)
    warning: str | None = None
    error: str | None = None
    redaction_counts: dict[str, int] = field(default_factory=dict)


async def process_document_ingestion(
    document_id: str,
    *,
    raise_errors: bool = False,
) -> IngestResult:
    """Extract, redact, embed, index, and entity-extract one stored document."""

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        if not document:
            if raise_errors:
                raise ValueError("Document not found")
            return IngestResult(
                document_id=document_id,
                status="failed",
                error="Document not found",
            )

        try:
            document.status = "processing"
            document.processing_error = None
            await session.commit()

            path = Path(document.storage_path)
            if not path.exists():
                raise FileNotFoundError("Stored file no longer exists")

            data = await asyncio.to_thread(path.read_bytes)
            pages = await extract_text(document.filename, data)
            chunks = split_chunks(pages)
            if not chunks:
                raise ValueError("No text extracted from document")

            redacted_chunks, redaction_counts = redact_chunks(chunks)
            vector_store = get_vector_store()
            embedder = get_embedding_provider()

            try:
                current_count = await vector_store.count()
            except Exception:  # pragma: no cover - defensive provider fallback
                current_count = 0

            existing_ids = list(document.pinecone_ids or [])
            projected = current_count - len(existing_ids) + len(redacted_chunks)
            warning: str | None = None
            if projected > PINECONE_FREE_TIER_LIMIT:
                raise RuntimeError(
                    "Embedding this document would push the Pinecone index to "
                    f"{projected} vectors, over the free-tier limit of "
                    f"{PINECONE_FREE_TIER_LIMIT}."
                )
            if projected > PINECONE_FREE_TIER_LIMIT * PINECONE_WARN_RATIO:
                warning = (
                    f"Approaching Pinecone free-tier limit: {projected}/"
                    f"{PINECONE_FREE_TIER_LIMIT} vectors after this upsert."
                )
                logger.warning(warning)

            if existing_ids:
                await vector_store.delete(existing_ids)

            vectors = await embedder.embed([chunk.text for chunk in redacted_chunks])
            records: list[VectorRecord] = []
            pinecone_ids: list[str] = []
            for chunk, vector in zip(redacted_chunks, vectors):
                vec_id = f"{document.id}:{chunk.index}"
                pinecone_ids.append(vec_id)
                records.append(
                    VectorRecord(
                        id=vec_id,
                        values=vector,
                        sparse_values=build_sparse_vector(chunk.text),
                        metadata={
                            "document_id": document.id,
                            "document_name": document.filename,
                            "document_type": document.document_type,
                            "chunk_index": chunk.index,
                            "page": chunk.page or 1,
                            "text": chunk.text,
                            "redacted": True,
                            "sparse_terms": sparse_keywords(chunk.text),
                        },
                    )
                )

            await vector_store.upsert(records)

            document.pinecone_ids = pinecone_ids
            document.chunk_count = len(redacted_chunks)
            document.redaction_counts = redaction_counts
            document.status = "indexed"
            document.processing_error = None

            full_text = "\n\n".join(text for _, text in pages)
            extracted = extract_entities(full_text)
            await session.execute(sa_delete(Entity).where(Entity.document_id == document.id))
            for ent in extracted:
                session.add(
                    Entity(
                        document_id=document.id,
                        entity_type=ent.entity_type,
                        entity_text=ent.entity_text[:512],
                        confidence=float(ent.confidence),
                    )
                )

            await session.commit()
            return IngestResult(
                document_id=document.id,
                status=document.status,
                chunk_count=document.chunk_count,
                pinecone_ids=pinecone_ids,
                warning=warning,
                redaction_counts=redaction_counts,
            )
        except Exception as exc:
            await session.rollback()
            document = await session.get(Document, document_id)
            if document:
                document.status = "failed"
                document.processing_error = str(exc)[:1024]
                await session.commit()
            if raise_errors:
                raise
            return IngestResult(document_id=document_id, status="failed", error=str(exc))

"""Aggregate query analytics from the queries table."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.query import Query


async def compute_analytics(session: AsyncSession) -> dict:
    total_queries: int = (
        await session.execute(select(func.count(Query.id)))
    ).scalar_one()

    if total_queries == 0:
        return {
            "total_queries": 0,
            "avg_latency_ms": 0.0,
            "queries_per_document": [],
            "top_questions": [],
        }

    avg_latency: float = (
        await session.execute(select(func.avg(Query.latency_ms)))
    ).scalar_one() or 0.0

    avg_confidence: float = (
        await session.execute(select(func.avg(Query.confidence)))
    ).scalar_one() or 0.0

    # Queries per document = count of times a document_id appears in any
    # query's retrieved_chunks JSON.
    rows = (
        await session.execute(
            select(Query.retrieved_chunks, Query.question, Query.timestamp)
        )
    ).all()

    per_doc_counter: Counter[str] = Counter()
    question_counter: Counter[str] = Counter()
    for chunks, question, _ in rows:
        seen_in_query: set[str] = set()
        for chunk in chunks or []:
            doc_id = chunk.get("document_id") if isinstance(chunk, dict) else None
            if doc_id and doc_id not in seen_in_query:
                seen_in_query.add(doc_id)
                per_doc_counter[doc_id] += 1
        if question:
            question_counter[question.strip()] += 1

    # Resolve document names for the per-document counts.
    doc_names: Dict[str, str] = {}
    if per_doc_counter:
        docs = (
            await session.execute(
                select(Document.id, Document.filename).where(
                    Document.id.in_(list(per_doc_counter.keys()))
                )
            )
        ).all()
        doc_names = {row[0]: row[1] for row in docs}

    queries_per_document: List[dict] = [
        {
            "document_id": doc_id,
            "document_name": doc_names.get(doc_id, "(deleted)"),
            "query_count": count,
        }
        for doc_id, count in per_doc_counter.most_common()
    ]

    top_questions: List[dict] = [
        {"question": q, "count": count}
        for q, count in question_counter.most_common(5)
    ]

    return {
        "total_queries": int(total_queries),
        "avg_latency_ms": float(round(avg_latency, 2)),
        "avg_confidence": float(round(avg_confidence, 4)),
        "queries_per_document": queries_per_document,
        "top_questions": top_questions,
    }

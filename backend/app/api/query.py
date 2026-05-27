"""RAG query endpoint."""
from __future__ import annotations

import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import chat_dep, embedding_dep, session_dep, vector_dep
from app.core.config import get_settings
from app.models.query import Query
from app.models.session import Session as ChatSession
from app.schemas.query import Citation, QueryHistoryItem, QueryRequest, QueryResponse
from app.services.embeddings import EmbeddingProvider
from app.services.llm import SYSTEM_PROMPT, ChatProvider, ContextSnippet, build_user_prompt
from app.services.risk_flags import detect_risk_flags
from app.services.vector_store import VectorStore

router = APIRouter(tags=["query"])


def _confidence_from_scores(scores: List[float]) -> float:
    """Average top scores, clipped into [0, 1]."""
    if not scores:
        return 0.0
    avg = sum(scores) / len(scores)
    return max(0.0, min(1.0, float(avg)))


@router.post("/query", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    session: AsyncSession = Depends(session_dep),
    embedder: EmbeddingProvider = Depends(embedding_dep),
    vector_store: VectorStore = Depends(vector_dep),
    chat: ChatProvider = Depends(chat_dep),
) -> QueryResponse:
    settings = get_settings()
    top_k = max(1, min(payload.top_k or settings.top_k, 20))

    chat_session: ChatSession | None = None
    if payload.session_id:
        chat_session = await session.get(ChatSession, payload.session_id)
        if not chat_session:
            raise HTTPException(status_code=404, detail="Session not found")
    if chat_session is None:
        chat_session = ChatSession(document_ids=payload.document_ids or [])
        session.add(chat_session)
        await session.flush()

    document_ids = payload.document_ids or chat_session.document_ids or None

    started = time.perf_counter()
    [query_vector] = await embedder.embed([payload.question])
    matches = await vector_store.query(
        query_vector, top_k=top_k, document_ids=document_ids
    )

    citations: List[Citation] = []
    snippets: List[ContextSnippet] = []
    for idx, match in enumerate(matches, start=1):
        meta = match.metadata or {}
        text = str(meta.get("text", ""))
        label = f"Doc {idx}"
        citations.append(
            Citation(
                chunk_id=match.id,
                document_id=str(meta.get("document_id", "")),
                document_name=str(meta.get("document_name", "unknown")),
                chunk_index=int(meta.get("chunk_index", 0)),
                text=text,
                score=float(match.score),
                page=int(meta["page"]) if meta.get("page") is not None else None,
            )
        )
        snippets.append(ContextSnippet(label=label, text=text))

    user_prompt = build_user_prompt(payload.question, snippets)
    answer = await chat.complete(SYSTEM_PROMPT, user_prompt)
    latency_ms = int((time.perf_counter() - started) * 1000)

    confidence = _confidence_from_scores([c.score for c in citations])
    risk_flags = detect_risk_flags([payload.question, answer, *(c.text for c in citations)])

    record = Query(
        session_id=chat_session.id,
        question=payload.question,
        answer=answer,
        retrieved_chunks=[c.model_dump() for c in citations],
        latency_ms=latency_ms,
        confidence=confidence,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    return QueryResponse(
        id=record.id,
        session_id=chat_session.id,
        question=payload.question,
        answer=answer,
        citations=citations,
        confidence=confidence,
        latency_ms=latency_ms,
        risk_flags=risk_flags,
        timestamp=record.timestamp,
    )


@router.get("/queries", response_model=list[QueryHistoryItem])
async def list_queries(
    limit: int = 20,
    session_id: str | None = None,
    session: AsyncSession = Depends(session_dep),
) -> list[QueryHistoryItem]:
    stmt = select(Query).order_by(Query.timestamp.desc()).limit(max(1, min(limit, 200)))
    if session_id:
        stmt = stmt.where(Query.session_id == session_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        QueryHistoryItem(
            id=q.id,
            session_id=q.session_id,
            question=q.question,
            answer=q.answer,
            latency_ms=q.latency_ms,
            confidence=q.confidence,
            timestamp=q.timestamp,
        )
        for q in rows
    ]

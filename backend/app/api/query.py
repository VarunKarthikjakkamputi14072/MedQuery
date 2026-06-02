"""RAG query endpoint."""
from __future__ import annotations

import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import chat_dep, embedding_dep, session_dep, vector_dep
from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.query import Query
from app.models.session import Session as ChatSession
from app.schemas.query import Citation, QueryHistoryItem, QueryRequest, QueryResponse
from app.services.dedup import dedupe_matches
from app.services.embeddings import EmbeddingProvider
from app.services.fusion import reciprocal_rank_fusion
from app.services.lexical import keyword_search
from app.services.llm import (
    SYSTEM_PROMPT,
    ChatProvider,
    ContextSnippet,
    TurnHistory,
    build_user_prompt,
)
from app.services.risk_flags import detect_risk_flags
from app.services.vector_store import VectorMatch, VectorStore

router = APIRouter(tags=["query"])

HISTORY_TURNS = 3


async def _resolve_lexical_matches(
    session: AsyncSession, ids: List[str]
) -> dict[str, VectorMatch]:
    """Build VectorMatch objects for chunk ids that only the lexical arm found."""
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Chunk, Document.filename)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.id.in_(ids))
        )
    ).all()
    resolved: dict[str, VectorMatch] = {}
    for chunk, filename in rows:
        resolved[chunk.id] = VectorMatch(
            id=chunk.id,
            # Lexical-only hit: no cosine score. Confidence is computed from
            # vector scores, so leaving this at 0.0 keeps it out of that average.
            score=0.0,
            metadata={
                "document_id": chunk.document_id,
                "document_name": filename,
                "chunk_index": chunk.chunk_index,
                "page": chunk.page,
                "text": chunk.text,
            },
        )
    return resolved


async def retrieve_matches(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    question: str,
    document_ids: List[str] | None,
    top_k: int,
    hybrid: bool,
) -> List[VectorMatch]:
    """Vector retrieval, optionally fused with a BM25 lexical arm via RRF.

    Shared by the /query endpoint and the evaluation harness so both measure the
    same retrieval path.
    """
    pool = max(top_k * 4, 20)
    [query_vector] = await embedder.embed([question])
    vector_matches = await vector_store.query(
        query_vector, top_k=pool, document_ids=document_ids
    )

    if not hybrid:
        return dedupe_matches(vector_matches)[:top_k]

    lexical = await keyword_search(session, question, document_ids=document_ids, top_k=pool)
    vector_ids = [m.id for m in vector_matches]
    lexical_ids = [cid for cid, _ in lexical]
    fused = reciprocal_rank_fusion([vector_ids, lexical_ids])

    vec_by_id = {m.id: m for m in vector_matches}
    missing = [cid for cid, _ in fused if cid not in vec_by_id]
    lex_by_id = await _resolve_lexical_matches(session, missing)

    ordered: List[VectorMatch] = []
    for cid, _ in fused:
        match = vec_by_id.get(cid) or lex_by_id.get(cid)
        if match is not None:
            ordered.append(match)

    return dedupe_matches(ordered)[:top_k]


def _confidence_from_scores(scores: List[float]) -> float:
    if not scores:
        return 0.0
    avg = sum(scores) / len(scores)
    return max(0.0, min(1.0, float(avg)))


async def _recent_history(
    session: AsyncSession, session_id: str, limit: int = HISTORY_TURNS
) -> list[TurnHistory]:
    rows = (
        await session.execute(
            select(Query.question, Query.answer)
            .where(Query.session_id == session_id)
            .order_by(Query.timestamp.desc())
            .limit(limit)
        )
    ).all()
    # rows are newest first; flip so prompt reads oldest -> newest.
    return [TurnHistory(question=q, answer=a) for q, a in reversed(rows)]


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

    history = await _recent_history(session, chat_session.id)

    started = time.perf_counter()
    matches = await retrieve_matches(
        session,
        embedder,
        vector_store,
        payload.question,
        document_ids,
        top_k=top_k,
        hybrid=settings.use_hybrid_retrieval,
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

    user_prompt = build_user_prompt(payload.question, snippets, history=history)
    answer = await chat.complete(SYSTEM_PROMPT, user_prompt)
    latency_ms = int((time.perf_counter() - started) * 1000)

    # Confidence is derived from vector similarity; lexical-only hits (score 0)
    # are excluded so they don't drag the average down.
    confidence = _confidence_from_scores([c.score for c in citations if c.score > 0])
    risk = detect_risk_flags(
        [payload.question, answer, *(c.text for c in citations)]
    )

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
        risk_flag=risk.risk_flag,
        risk_flags=risk.matched_terms,
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

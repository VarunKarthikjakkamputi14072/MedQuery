"""Session management endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import session_dep
from app.models.query import Query
from app.models.session import Session as ChatSession
from app.schemas.query import QueryHistoryItem
from app.schemas.session import SessionCreate, SessionRead, SessionWithMessages

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionRead)
async def create_session(
    payload: SessionCreate,
    session: AsyncSession = Depends(session_dep),
) -> SessionRead:
    chat = ChatSession(document_ids=payload.document_ids)
    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return SessionRead.model_validate(chat)


@router.get("", response_model=List[SessionRead])
async def list_sessions(session: AsyncSession = Depends(session_dep)) -> List[SessionRead]:
    rows = (
        await session.execute(select(ChatSession).order_by(ChatSession.created_at.desc()))
    ).scalars().all()
    return [SessionRead.model_validate(s) for s in rows]


@router.get("/{session_id}", response_model=SessionWithMessages)
async def get_session(
    session_id: str,
    session: AsyncSession = Depends(session_dep),
) -> SessionWithMessages:
    chat = await session.get(ChatSession, session_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = (
        await session.execute(
            select(Query)
            .where(Query.session_id == session_id)
            .order_by(Query.timestamp.asc())
        )
    ).scalars().all()
    messages = [
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
    base = SessionRead.model_validate(chat)
    return SessionWithMessages(**base.model_dump(), messages=messages)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    session: AsyncSession = Depends(session_dep),
) -> Response:
    chat = await session.get(ChatSession, session_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Session not found")
    await session.execute(sa_delete(Query).where(Query.session_id == session_id))
    await session.delete(chat)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

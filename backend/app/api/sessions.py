"""Session management endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import session_dep
from app.models.session import Session as ChatSession
from app.schemas.session import SessionCreate, SessionRead

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
    rows = (await session.execute(select(ChatSession).order_by(ChatSession.created_at.desc()))).scalars().all()
    return [SessionRead.model_validate(s) for s in rows]


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    session: AsyncSession = Depends(session_dep),
) -> SessionRead:
    chat = await session.get(ChatSession, session_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead.model_validate(chat)

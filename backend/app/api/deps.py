"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session as _get_session
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.llm import ChatProvider, get_chat_provider
from app.services.storage import LocalStorage, get_storage
from app.services.vector_store import VectorStore, get_vector_store


async def session_dep() -> AsyncIterator[AsyncSession]:
    async for s in _get_session():
        yield s


def embedding_dep() -> EmbeddingProvider:
    return get_embedding_provider()


def chat_dep() -> ChatProvider:
    return get_chat_provider()


def vector_dep() -> VectorStore:
    return get_vector_store()


def storage_dep() -> LocalStorage:
    return get_storage()


__all__ = [
    "session_dep",
    "embedding_dep",
    "chat_dep",
    "vector_dep",
    "storage_dep",
    "Depends",
]

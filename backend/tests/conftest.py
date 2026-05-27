"""Pytest fixtures: spin up an isolated SQLite DB + in-memory vector store per test."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Configure environment BEFORE importing the app so settings pick it up.
TMP_DIR = tempfile.mkdtemp(prefix="medquery-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TMP_DIR}/test.db"
os.environ["STORAGE_DIR"] = f"{TMP_DIR}/storage"
os.environ["USE_FAKE_PROVIDERS"] = "true"
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("PINECONE_API_KEY", "")

from app.core.config import get_settings  # noqa: E402
from app.db.session import AsyncSessionLocal, engine, init_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import vector_store as vector_store_module  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def _prepare_db_and_store() -> AsyncIterator[None]:
    # Reset cached settings + vector store between tests.
    get_settings.cache_clear()
    vector_store_module.reset_vector_store()

    # Re-create DB tables per test for isolation.
    async with engine.begin() as conn:
        from app.db.session import Base

        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator:
    async with AsyncSessionLocal() as session:
        yield session

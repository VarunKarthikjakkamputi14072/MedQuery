"""FastAPI entrypoint for the MedQuery backend."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.documents import (
    documents_router,
    embed_router,
    extract_router,
    upload_router,
)
from app.api.query import router as query_router
from app.api.sessions import router as sessions_router
from app.core.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="MedQuery API",
        version="0.2.0",
        description="Clinical document intelligence — upload, embed, extract, and query medical records.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "medquery",
            "fake_providers": settings.use_fake_providers,
        }

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {"service": "medquery", "docs": "/docs"}

    app.include_router(upload_router)
    app.include_router(embed_router)
    app.include_router(extract_router)
    app.include_router(query_router)
    app.include_router(documents_router)
    app.include_router(sessions_router)
    app.include_router(analytics_router)

    return app


app = create_app()

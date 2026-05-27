"""Celery worker entrypoint for asynchronous document ingestion."""
from __future__ import annotations

import asyncio

from celery import Celery

from app.core.config import get_settings
from app.services.ingestion import process_document_ingestion

settings = get_settings()
broker_url = settings.celery_broker_url or settings.redis_url
result_backend = settings.celery_result_backend or settings.redis_url

celery_app = Celery("medquery", broker=broker_url, backend=result_backend)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
)


@celery_app.task(name="medquery.process_document_ingestion")
def process_document_ingestion_task(document_id: str) -> dict:
    result = asyncio.run(process_document_ingestion(document_id, raise_errors=True))
    return {
        "document_id": result.document_id,
        "status": result.status,
        "chunk_count": result.chunk_count,
        "pinecone_ids": result.pinecone_ids,
        "warning": result.warning,
        "error": result.error,
        "redaction_counts": result.redaction_counts,
    }

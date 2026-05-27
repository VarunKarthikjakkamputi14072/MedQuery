"""Task dispatch helpers for document ingestion."""
from __future__ import annotations

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.services.ingestion import process_document_ingestion


def enqueue_document_ingestion(
    document_id: str,
    background_tasks: BackgroundTasks | None = None,
) -> str | None:
    settings = get_settings()
    if settings.ingest_queue_backend == "celery":
        from app.worker import process_document_ingestion_task

        task = process_document_ingestion_task.delay(document_id)
        return str(task.id)

    if background_tasks is not None:
        background_tasks.add_task(process_document_ingestion, document_id)
        return "fastapi-background"

    return None

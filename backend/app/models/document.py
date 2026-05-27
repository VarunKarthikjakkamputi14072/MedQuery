"""Document ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Clinical Note")
    upload_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pinecone_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    redaction_counts: Mapped[Dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    processing_error: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

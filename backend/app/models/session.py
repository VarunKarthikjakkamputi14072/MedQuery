"""Chat session ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    document_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)

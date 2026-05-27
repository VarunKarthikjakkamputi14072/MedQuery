"""Session API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    document_ids: List[str] = Field(default_factory=list)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    document_ids: List[str]

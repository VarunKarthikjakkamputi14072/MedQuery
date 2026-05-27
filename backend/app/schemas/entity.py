"""Entity API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, ConfigDict


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    entity_type: str
    entity_text: str
    confidence: float
    created_at: datetime


class ExtractResponse(BaseModel):
    document_id: str
    entities: List[EntityRead]
    summary: Dict[str, int]

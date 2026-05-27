"""Document API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

DOCUMENT_TYPES = [
    "Discharge Summary",
    "Lab Report",
    "Clinical Note",
    "Radiology Report",
]


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    document_type: str
    upload_timestamp: datetime
    chunk_count: int
    pinecone_ids: List[str]
    redaction_counts: Dict[str, int] = Field(default_factory=dict)
    size_bytes: int
    status: str
    processing_error: Optional[str] = None


class UploadResponse(BaseModel):
    document: DocumentRead
    preview: str
    task_id: Optional[str] = None


class EmbedRequest(BaseModel):
    document_id: str


class EmbedResponse(BaseModel):
    document_id: str
    chunk_count: int
    pinecone_ids: List[str]
    warning: Optional[str] = None
    status: str = "indexed"
    error: Optional[str] = None

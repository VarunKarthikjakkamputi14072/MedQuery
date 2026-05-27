"""Document API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict

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
    size_bytes: int
    status: str


class UploadResponse(BaseModel):
    document: DocumentRead
    preview: str


class EmbedRequest(BaseModel):
    document_id: str


class EmbedResponse(BaseModel):
    document_id: str
    chunk_count: int
    pinecone_ids: List[str]

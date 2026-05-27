"""Query API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    text: str
    score: float
    page: Optional[int] = None


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    top_k: int = 5


class QueryResponse(BaseModel):
    id: str
    session_id: str
    question: str
    answer: str
    citations: List[Citation]
    confidence: float
    latency_ms: int
    risk_flags: List[str] = Field(default_factory=list)
    timestamp: datetime


class QueryHistoryItem(BaseModel):
    id: str
    session_id: str
    question: str
    answer: str
    latency_ms: int
    confidence: float
    timestamp: datetime

"""Analytics API schemas."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel


class DocumentUsage(BaseModel):
    document_id: str
    document_name: str
    query_count: int


class TopQuestion(BaseModel):
    question: str
    count: int


class AnalyticsResponse(BaseModel):
    total_queries: int
    avg_latency_ms: float
    avg_confidence: float = 0.0
    queries_per_document: List[DocumentUsage]
    top_questions: List[TopQuestion]

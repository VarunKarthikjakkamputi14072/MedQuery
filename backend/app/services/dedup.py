"""Deduplicate retrieved vector matches by content hash."""
from __future__ import annotations

import hashlib
from typing import Iterable, List

from app.services.vector_store import VectorMatch


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def dedupe_matches(matches: Iterable[VectorMatch]) -> List[VectorMatch]:
    """Return matches in order, dropping any whose text hash was already seen.

    LangChain's overlapping chunks can return near-duplicate context to the
    LLM; we hash the normalised chunk text and keep only the first occurrence.
    """
    seen: set[str] = set()
    deduped: List[VectorMatch] = []
    for match in matches:
        text = str((match.metadata or {}).get("text", ""))
        if not text.strip():
            continue
        digest = _hash(text)
        if digest in seen:
            continue
        seen.add(digest)
        deduped.append(match)
    return deduped

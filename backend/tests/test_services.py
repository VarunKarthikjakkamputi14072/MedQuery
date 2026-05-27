"""Service-level unit tests for chunking + risk flag detection."""
from __future__ import annotations

import pytest

from app.services.risk_flags import detect_risk_flags
from app.services.text_extraction import split_chunks


def test_chunking_returns_overlapping_pieces():
    page_text = ("clinical narrative " * 400).strip()
    chunks = split_chunks([(1, page_text)])
    assert len(chunks) >= 2
    assert all(c.page == 1 for c in chunks)
    assert all(c.text for c in chunks)


def test_risk_flag_detection_dedupes():
    found = detect_risk_flags(
        [
            "Patient developed Sepsis and hypoxia overnight.",
            "Repeat exam confirms sepsis without bleeding.",
        ]
    )
    assert "sepsis" in found
    assert "hypoxia" in found
    # Ensure no duplicate entries.
    assert len(found) == len(set(found))


@pytest.mark.asyncio
async def test_fake_embedding_provider_is_deterministic():
    from app.services.embeddings import FakeEmbeddingProvider

    provider = FakeEmbeddingProvider()
    a = await provider.embed(["hello world"])
    b = await provider.embed(["hello world"])
    assert a == b
    assert len(a[0]) == provider.dimension

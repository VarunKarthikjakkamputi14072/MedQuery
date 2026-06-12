"""Service-level unit tests."""
from __future__ import annotations

import pytest

from app.services.dedup import dedupe_matches
from app.services.entity_extraction import extract_entities
from app.services.retry import retry_async
from app.services.risk_flags import detect_risk_flags
from app.services.text_extraction import split_chunks
from app.services.vector_store import VectorMatch


def test_chunking_returns_overlapping_pieces():
    page_text = ("clinical narrative " * 400).strip()
    chunks = split_chunks([(1, page_text)])
    assert len(chunks) >= 2
    assert all(c.page == 1 for c in chunks)
    assert all(c.text for c in chunks)


def test_risk_flag_detection_uses_required_list():
    result = detect_risk_flags(
        [
            "Patient developed sepsis overnight, status critical.",
            "Code Blue was called STAT.",
            "Family confirmed DNR status earlier this week.",
        ]
    )
    assert result.risk_flag is True
    # Canonical casing preserved + order matches HIGH_RISK_TERMS.
    assert result.matched_terms == ["critical", "STAT", "sepsis", "DNR", "code blue"]


def test_risk_flag_detection_no_match():
    result = detect_risk_flags(["Patient is stable and ambulating."])
    assert result.risk_flag is False
    assert result.matched_terms == []


def test_dedupe_drops_repeat_chunks():
    matches = [
        VectorMatch(id="a", score=0.9, metadata={"text": "Sepsis with hypotension."}),
        VectorMatch(id="b", score=0.85, metadata={"text": "sepsis with hypotension."}),
        VectorMatch(id="c", score=0.8, metadata={"text": "Lactate 4.2 mmol/L."}),
    ]
    deduped = dedupe_matches(matches)
    assert [m.id for m in deduped] == ["a", "c"]


@pytest.mark.asyncio
async def test_fake_embedding_provider_is_deterministic():
    from app.services.embeddings import FakeEmbeddingProvider

    provider = FakeEmbeddingProvider()
    a = await provider.embed(["hello world"])
    b = await provider.embed(["hello world"])
    assert a == b
    assert len(a[0]) == provider.dimension


@pytest.mark.asyncio
async def test_retry_async_retries_then_succeeds():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("boom")
        return "ok"

    result = await retry_async(flaky, delays=(0.0, 0.0, 0.0), label="test")
    assert result == "ok"
    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_retry_async_eventually_raises():
    async def always_fails():
        raise TimeoutError("nope")

    with pytest.raises(TimeoutError):
        await retry_async(always_fails, delays=(0.0,), label="test")


def test_entity_extraction_regex_backend():
    text = (
        "Patient presents with pneumonia and acute kidney injury. "
        "Started on vancomycin 1 g IV every 12 hours and metformin 500 mg PO. "
        "Procedures: intubation and central line placement. "
        "Labs: WBC 14.2 x10^3/uL, Cr 1.8 mg/dL, Lactate 3.4 mmol/L."
    )
    entities = extract_entities(text)
    types = {e.entity_type for e in entities}
    texts = {e.entity_text.lower() for e in entities}

    assert "diagnosis" in types
    assert "medication" in types
    assert "procedure" in types
    assert "lab_value" in types
    assert "pneumonia" in texts
    assert any("wbc" in t for t in texts)


def test_reciprocal_rank_fusion():
    from app.services.fusion import reciprocal_rank_fusion

    ranking1 = ["docA", "docB", "docC"]
    ranking2 = ["docB", "docD", "docA"]

    fused = reciprocal_rank_fusion([ranking1, ranking2], k=60)

    assert len(fused) == 4
    assert fused[0][0] == "docB"
    assert fused[1][0] == "docA"
    
    scores = dict(fused)
    assert scores["docB"] > scores["docA"]
    assert scores["docA"] > scores["docC"]
    assert scores["docA"] > scores["docD"]

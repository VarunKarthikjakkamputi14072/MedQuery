"""Tests for the hybrid retrieval pieces: BM25, RRF fusion, and the eval harness."""
from __future__ import annotations

from app.services.fusion import reciprocal_rank_fusion
from app.services.lexical import bm25_rank
from eval.run_eval import run


def test_bm25_ranks_exact_term_first():
    corpus = [
        ("a", "The cardiomediastinal silhouette is within normal limits."),
        ("b", "Most recent labs show an HbA1c of 8.2 percent and fasting glucose."),
        ("c", "Patient counseled on dietary changes and home glucose monitoring."),
    ]
    ranked = bm25_rank("What was the HbA1c value?", corpus, top_k=3)
    assert ranked, "expected at least one match"
    assert ranked[0][0] == "b"


def test_bm25_empty_corpus():
    assert bm25_rank("anything", [], top_k=5) == []


def test_rrf_rewards_agreement_across_rankings():
    # 'x' is high in both lists; 'z' only appears once.
    vector = ["x", "y", "z"]
    lexical = ["x", "w", "y"]
    fused = reciprocal_rank_fusion([vector, lexical])
    ids = [i for i, _ in fused]
    assert ids[0] == "x"
    # 'y' appears in both lists, so it should outrank singletons 'z' and 'w'.
    assert ids.index("y") < ids.index("z")


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == []


async def test_eval_harness_hybrid_beats_vector_only():
    results = await run()
    assert set(results) == {"vector", "lexical", "hybrid"}
    # On the labeled fixtures, fusing the lexical arm should never do worse than
    # vector-only, and should retrieve something.
    assert results["hybrid"]["recall"] >= results["vector"]["recall"]
    assert results["hybrid"]["recall"] > 0

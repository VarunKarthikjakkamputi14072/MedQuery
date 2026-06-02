"""Reciprocal Rank Fusion for combining rankings from different retrievers.

RRF merges several ranked lists without needing their scores to be on the same
scale — which is exactly the situation with cosine similarity and BM25. Each item
gets 1 / (k + rank) from every list it appears in, and the sums are sorted. It's
simple, has one parameter, and is hard to beat as a default fusion method.
"""
from __future__ import annotations

from collections import defaultdict
from typing import List, Sequence, Tuple

# Standard RRF constant from the original paper; damps the weight of top ranks.
RRF_K = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = RRF_K
) -> List[Tuple[str, float]]:
    """Fuse ranked id lists into one ordering.

    Args:
        rankings: each inner sequence is a list of ids ordered best-first.
        k: RRF damping constant.

    Returns:
        (id, fused_score) pairs, best-first.
    """
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] += 1.0 / (k + rank + 1)

    fused = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return fused

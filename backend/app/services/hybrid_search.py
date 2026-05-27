"""Sparse keyword features used alongside dense vector retrieval."""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Dict, List, TypedDict


class SparseVector(TypedDict):
    indices: List[int]
    values: List[float]


TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+./-]*|\d+(?:\.\d+)?")
SPARSE_HASH_SPACE = 2_147_483_647
BM25_K1 = 1.5
BM25_B = 0.75
DEFAULT_ALPHA = 0.72

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "patient",
    "the",
    "to",
    "was",
    "were",
    "with",
}


def tokenize_sparse(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


def _hash_token(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % SPARSE_HASH_SPACE


def build_sparse_vector(text: str, max_terms: int = 128) -> SparseVector | None:
    """Build a hashed BM25-style sparse vector for Pinecone hybrid queries."""

    counts = Counter(tokenize_sparse(text))
    if not counts:
        return None

    doc_len = sum(counts.values()) or 1
    avgdl = max(doc_len, 1)
    weighted: Dict[int, float] = {}
    for token, count in counts.most_common(max_terms):
        # BM25 term-frequency saturation. Corpus-wide IDF is unavailable at
        # chunk build time, so exact rare clinical tokens still get boosted
        # through hashed term overlap while dense embeddings carry semantics.
        numerator = count * (BM25_K1 + 1)
        denominator = count + BM25_K1 * (1 - BM25_B + BM25_B * (doc_len / avgdl))
        value = numerator / denominator
        index = _hash_token(token)
        weighted[index] = weighted.get(index, 0.0) + float(value)

    indices = sorted(weighted)
    values = [weighted[index] for index in indices]
    return {"indices": indices, "values": values}


def sparse_keywords(text: str, max_terms: int = 32) -> list[str]:
    counts = Counter(tokenize_sparse(text))
    return [token for token, _ in counts.most_common(max_terms)]


def sparse_dot(query: SparseVector | None, document: SparseVector | None) -> float:
    if not query or not document:
        return 0.0

    doc_values = dict(zip(document["indices"], document["values"]))
    return sum(
        value * doc_values.get(index, 0.0)
        for index, value in zip(query["indices"], query["values"])
    )


def scale_sparse_vector(vector: SparseVector | None, weight: float) -> SparseVector | None:
    if not vector:
        return None
    return {
        "indices": list(vector["indices"]),
        "values": [value * weight for value in vector["values"]],
    }


def squash_sparse_score(score: float) -> float:
    if score <= 0:
        return 0.0
    return score / (score + 1.0)


def combine_dense_sparse(
    dense_score: float,
    sparse_score: float,
    alpha: float = DEFAULT_ALPHA,
) -> float:
    dense = max(0.0, min(1.0, dense_score))
    sparse = squash_sparse_score(sparse_score)
    return alpha * dense + (1.0 - alpha) * sparse


def sparse_vector_norm(vector: SparseVector | None) -> float:
    if not vector:
        return 0.0
    return math.sqrt(sum(value * value for value in vector["values"]))

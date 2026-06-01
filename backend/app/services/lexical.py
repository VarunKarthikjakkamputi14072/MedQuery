"""Lexical (keyword) retrieval over persisted chunks, using BM25.

Vector search alone misses exact clinical terms and acronyms — if a query says
"HbA1c" or "BP 140/90", semantic similarity can rank a loosely-related chunk
above the one that literally contains the term. BM25 over the chunk text covers
that case; the results are fused with the vector results in the query endpoint.

This is a compact pure-Python BM25 scored over the chunks in scope. It keeps the
lexical arm portable (Postgres + SQLite) and dependency-free. For a larger corpus
the natural step is Postgres full-text search (`to_tsvector`/`ts_rank`); noted in
the README.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Standard BM25 parameters.
_K1 = 1.5
_B = 0.75

# Dropping common words matters here: on a small corpus a stopword like "the"
# can look as rare (and so as informative) as a real term like "hba1c", which
# skews ranking. This is a compact English stopword list, enough for queries.
_STOPWORDS = frozenset(
    """
    a an and are as at be by for from has have how in into is it its of on or
    that the their this to was were what when where which who will with would
    do does did you your we our they them then than there here about over under
    """.split()
)


def _tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


async def _fetch_chunks(
    session: AsyncSession, document_ids: Optional[Sequence[str]]
) -> List[Tuple[str, str]]:
    stmt = select(Chunk.id, Chunk.text)
    if document_ids:
        stmt = stmt.where(Chunk.document_id.in_(list(document_ids)))
    rows = (await session.execute(stmt)).all()
    return [(cid, text) for cid, text in rows]


def bm25_rank(
    query: str, corpus: Sequence[Tuple[str, str]], top_k: int = 20
) -> List[Tuple[str, float]]:
    """Rank (id, text) pairs against the query with BM25. Pure function for tests."""
    docs = [(cid, _tokenize(text)) for cid, text in corpus]
    docs = [(cid, toks) for cid, toks in docs if toks]
    if not docs:
        return []

    n = len(docs)
    doc_freq: Counter[str] = Counter()
    for _, toks in docs:
        for term in set(toks):
            doc_freq[term] += 1
    avg_len = sum(len(toks) for _, toks in docs) / n

    query_terms = _tokenize(query)
    scored: List[Tuple[str, float]] = []
    for cid, toks in docs:
        term_freq = Counter(toks)
        length = len(toks)
        score = 0.0
        for term in query_terms:
            freq = term_freq.get(term)
            if not freq:
                continue
            idf = math.log(1 + (n - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += idf * (freq * (_K1 + 1)) / (
                freq + _K1 * (1 - _B + _B * length / avg_len)
            )
        if score > 0:
            scored.append((cid, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


async def keyword_search(
    session: AsyncSession,
    query: str,
    document_ids: Optional[Sequence[str]] = None,
    top_k: int = 20,
) -> List[Tuple[str, float]]:
    """Return the top_k chunk ids (with BM25 scores) for the query."""
    corpus = await _fetch_chunks(session, document_ids)
    return bm25_rank(query, corpus, top_k=top_k)

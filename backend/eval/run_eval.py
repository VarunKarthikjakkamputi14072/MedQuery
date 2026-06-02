"""Retrieval evaluation harness.

Ingests a small labeled fixture set and measures retrieval quality for three
modes — vector-only, lexical-only (BM25), and hybrid (RRF fusion) — reporting
recall@k and MRR@k for each.

Run it:

    cd backend
    python -m eval.run_eval

By default it runs with the deterministic fake embedding provider, which is
*hash-based*, not semantic — so the vector-only numbers are essentially a random
baseline and the point it demonstrates is that the lexical/hybrid arms recover
exact clinical terms. For real semantic numbers, set OPENAI_API_KEY and
USE_FAKE_PROVIDERS=false before running; the harness uses whatever provider is
configured.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List

# Isolate the harness from any real DB/storage unless the caller set them.
_TMP = tempfile.mkdtemp(prefix="medquery-eval-")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP}/eval.db")
os.environ.setdefault("STORAGE_DIR", f"{_TMP}/storage")
os.environ.setdefault("USE_FAKE_PROVIDERS", "true")

from app.api.query import retrieve_matches  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import AsyncSessionLocal, init_db  # noqa: E402
from app.models.chunk import Chunk  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.services.embeddings import get_embedding_provider  # noqa: E402
from app.services.lexical import keyword_search  # noqa: E402
from app.services.vector_store import (  # noqa: E402
    VectorRecord,
    get_vector_store,
    reset_vector_store,
)
from sqlalchemy import delete as sa_delete  # noqa: E402

FIXTURES_PATH = Path(__file__).parent / "fixtures.json"
RESULTS_PATH = Path(__file__).parent / "results.json"


def _load_fixtures() -> dict:
    return json.loads(FIXTURES_PATH.read_text())


def recall_at_k(retrieved: List[str], gold: List[str]) -> float:
    if not gold:
        return 0.0
    hits = len(set(retrieved) & set(gold))
    return hits / len(gold)


def mrr_at_k(retrieved: List[str], gold: List[str]) -> float:
    gold_set = set(gold)
    for rank, item in enumerate(retrieved, start=1):
        if item in gold_set:
            return 1.0 / rank
    return 0.0


async def _ingest(session, embedder, vector_store, data: dict) -> None:
    reset_vector_store()
    await init_db()

    for doc in data["documents"]:
        # Re-runnable: clear any prior fixture rows for this document id.
        await session.execute(sa_delete(Chunk).where(Chunk.document_id == doc["id"]))
        await session.execute(sa_delete(Document).where(Document.id == doc["id"]))

        texts = doc["chunks"]
        vectors = await embedder.embed(texts)

        session.add(
            Document(
                id=doc["id"],
                filename=doc["name"],
                document_type=doc.get("type", "Clinical Note"),
                chunk_count=len(texts),
                pinecone_ids=[f"{doc['id']}:{i}" for i in range(len(texts))],
                storage_path="",
                size_bytes=0,
                status="indexed",
            )
        )
        records = []
        for i, (text, vector) in enumerate(zip(texts, vectors)):
            chunk_id = f"{doc['id']}:{i}"
            records.append(
                VectorRecord(
                    id=chunk_id,
                    values=vector,
                    metadata={
                        "document_id": doc["id"],
                        "document_name": doc["name"],
                        "chunk_index": i,
                        "page": 1,
                        "text": text,
                    },
                )
            )
            session.add(
                Chunk(
                    id=chunk_id,
                    document_id=doc["id"],
                    chunk_index=i,
                    page=1,
                    text=text,
                )
            )
        await vector_store.upsert(records)

    await session.commit()


async def run(k: int | None = None) -> Dict[str, Dict[str, float]]:
    """Run the eval and return {mode: {recall, mrr}} averaged over questions."""
    settings = get_settings()
    k = k or settings.top_k
    data = _load_fixtures()

    embedder = get_embedding_provider()
    vector_store = get_vector_store()

    async with AsyncSessionLocal() as session:
        await _ingest(session, embedder, vector_store, data)

        totals = {
            "vector": {"recall": 0.0, "mrr": 0.0},
            "lexical": {"recall": 0.0, "mrr": 0.0},
            "hybrid": {"recall": 0.0, "mrr": 0.0},
        }
        questions = data["questions"]
        for item in questions:
            question, gold = item["q"], item["gold"]

            vector_ids = [
                m.id
                for m in await retrieve_matches(
                    session, embedder, vector_store, question, None, k, hybrid=False
                )
            ]
            hybrid_ids = [
                m.id
                for m in await retrieve_matches(
                    session, embedder, vector_store, question, None, k, hybrid=True
                )
            ]
            lexical_ids = [
                cid for cid, _ in await keyword_search(session, question, None, top_k=k)
            ]

            for mode, ids in (
                ("vector", vector_ids),
                ("lexical", lexical_ids),
                ("hybrid", hybrid_ids),
            ):
                totals[mode]["recall"] += recall_at_k(ids, gold)
                totals[mode]["mrr"] += mrr_at_k(ids, gold)

        n = len(questions)
        return {
            mode: {metric: round(value / n, 4) for metric, value in scores.items()}
            for mode, scores in totals.items()
        }


def _print_table(k: int, results: Dict[str, Dict[str, float]]) -> None:
    settings = get_settings()
    provider = (
        "fake embeddings"
        if settings.use_fake_providers
        else settings.openai_embedding_model
    )
    print(f"\nRetrieval evaluation (k={k}, {provider})")
    print(f"{'mode':<10}{'recall@k':>12}{'MRR@k':>10}")
    print("-" * 32)
    for mode in ("vector", "lexical", "hybrid"):
        r = results[mode]
        print(f"{mode:<10}{r['recall']:>12.3f}{r['mrr']:>10.3f}")
    print()


def main() -> None:
    k = get_settings().top_k
    results = asyncio.run(run(k))
    _print_table(k, results)
    RESULTS_PATH.write_text(json.dumps({"k": k, "results": results}, indent=2))
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()

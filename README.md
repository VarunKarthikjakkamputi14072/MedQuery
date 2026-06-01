# MedQuery — Clinical Document Intelligence

A full-stack RAG (retrieval augmented generation) system for clinical
documents. Upload discharge summaries, lab reports, clinical notes, and
radiology reports; MedQuery extracts text, chunks it, embeds it into a
vector store, mines medical entities, and answers grounded clinical
questions with source citations, latency / confidence tracking, and a
high-risk content banner.

Retrieval is **hybrid** — vector similarity fused with a BM25 lexical arm — and
there's an **evaluation harness** that measures it, so "grounded, low-hallucination"
is something I can put numbers behind rather than just claim. See
[Retrieval design](#retrieval-design) and [Evaluation](#evaluation).

## Architecture

```
Next.js 14 + Tailwind (frontend)
        │
        ▼
FastAPI backend (async)
        │
        ├──► Local filesystem (mock S3) for uploaded PDFs/TXT
        ├──► PostgreSQL (documents, sessions, queries, entities, chunks)
        ├──► LangChain RecursiveCharacterTextSplitter (512 / 50 tokens)
        ├──► spaCy / scispaCy en_core_sci_sm (+ regex fallback)  → entities
        ├──► OpenAI text-embedding-3-small (embeddings, with retries)
        ├──► Pinecone serverless index "medquery" (batched upserts ≤100)
        ├──► Hybrid retrieval: vector (Pinecone) + BM25 lexical, fused with RRF
        └──► OpenAI gpt-4o-mini (multi-turn, with retries)
```

The embedding provider, vector store, and chat LLM all have **drop-in
fakes** that activate automatically when no API key is configured
(`USE_FAKE_PROVIDERS=true` by default). The entity extractor falls back
to a deterministic regex/keyword backend when scispaCy isn't installed.
This means the full pipeline runs end-to-end locally with zero external
dependencies and is fully covered by integration tests.

## Repository layout

```
backend/   FastAPI service, SQLAlchemy models, services + tests
frontend/  Next.js 14 (App Router) + Tailwind dark clinical UI
docker-compose.yml   postgresql + fastapi-backend + nextjs-frontend
.env.example         Shared env keys consumed by docker-compose
```

## Backend

### Endpoints

| Method | Path                            | Description                                                                                          |
| ------ | ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| POST   | `/upload`                       | Accepts PDF/TXT (max 10 MB), stores in mock-S3 dir, extracts text + chunks via LangChain (512/50)    |
| POST   | `/embed`                        | Embeds chunks via `text-embedding-3-small`, batched Pinecone upserts (≤100), free-tier cap warning   |
| POST   | `/extract`                      | spaCy `en_core_sci_sm` (or regex fallback) → medications, diagnoses, procedures, lab values          |
| POST   | `/query`                        | Hybrid retrieval (vector + BM25, RRF-fused), deduped by content hash, last 3 turns as context, returns answer + citations + risk |
| GET    | `/documents`                    | List uploaded documents with metadata                                                                |
| GET    | `/documents/{id}`               | Document metadata                                                                                    |
| GET    | `/documents/{id}/entities`      | All extracted entities for a document                                                                |
| DELETE | `/documents/{id}`               | Removes the document, its vectors, and entities                                                      |
| GET    | `/queries`                      | Recent queries (filterable by `session_id`)                                                          |
| GET    | `/analytics`                    | `total_queries`, `avg_latency_ms`, `avg_confidence`, `queries_per_document`, `top_questions`         |
| POST   | `/sessions`                     | Create chat session                                                                                  |
| GET    | `/sessions`                     | List sessions                                                                                        |
| GET    | `/sessions/{id}`                | Fetch a session with its messages                                                                    |
| DELETE | `/sessions/{id}`                | Delete session and cascade its queries                                                               |
| GET    | `/health`                       | Liveness probe                                                                                       |

All endpoints are `async`. CORS allows `http://localhost:3000` by default.

### Database schema (PostgreSQL via SQLAlchemy 2.0 async)

- `documents` — id, filename, document_type, upload_timestamp, chunk_count, pinecone_ids, storage_path, size_bytes, status
- `sessions` — id, created_at, document_ids
- `queries` — id, session_id, question, answer, retrieved_chunks, latency_ms, confidence, timestamp
- `entities` — id, document_id (FK), entity_type, entity_text, confidence, created_at
- `chunks` — id (`{document_id}:{index}`), document_id (FK), chunk_index, page, text

Models work against both Postgres (production) and SQLite (tests).

### Hardening (the known-issue checklist)

1. **Pinecone free-tier cap (100k vectors)** — `/embed` reads the index
   vector count first; soft-warns at 90 % and refuses with HTTP 507 if
   the upsert would exceed the limit. The warning surfaces in the
   dashboard + upload UI.
2. **Scanned-PDF detection** — `extract_text` raises
   `ScannedPdfError` (→ HTTP 422) if the combined extracted text from a
   PDF is shorter than 100 characters.
3. **OpenAI rate limits** — every embedding and chat call is wrapped in
   an async exponential-backoff retry (3 attempts: 2 s / 4 s / 8 s).
4. **Duplicate retrieved context** — `dedupe_matches` SHA-256 hashes the
   normalised chunk text and drops any repeats from LangChain's
   overlapping windows before the LLM sees them.
5. **Pinecone upsert batch limit (100)** — vectors are chunked into
   100-vector batches both for upsert and delete operations.
6. **CORS** — FastAPI `CORSMiddleware` configured for
   `http://localhost:3000` (configurable via `CORS_ORIGINS`).

### Retrieval design

Early on, retrieval was pure vector similarity. That works for paraphrased
questions but falls down on the things clinical text is full of — exact terms,
acronyms, and numbers. Ask for "HbA1c" or "creatinine" and a semantic match can
float a loosely-related chunk above the one that literally contains the value.

So retrieval is now **hybrid**:

1. **Vector arm** — embed the question, pull the nearest chunks from the vector
   store (Pinecone, or the in-memory cosine store in fake mode).
2. **Lexical arm** — a BM25 search over the chunk text persisted in Postgres
   (`app/services/lexical.py`). This is what catches the exact-term cases.
3. **Fusion** — the two rankings are combined with **Reciprocal Rank Fusion**
   (`app/services/fusion.py`). RRF doesn't need the cosine and BM25 scores to be
   on the same scale, which is the whole problem with naively mixing them; it just
   rewards chunks that rank well in either list.

To make the lexical arm possible, chunk text is now persisted to a `chunks` table
during `/embed` (it used to live only in the vector metadata). The chunk id is
`{document_id}:{index}` — the same id used as the vector id — so the two arms fuse
on a shared key. Hybrid is on by default and can be toggled with
`USE_HYBRID_RETRIEVAL=false`.

The BM25 implementation is a compact pure-Python one so the lexical arm stays
portable and dependency-free (and runs in tests on SQLite). For a larger corpus
the natural next step is Postgres full-text search (`to_tsvector`/`ts_rank`).

### Evaluation

A RAG system is only as good as its retrieval, so there's a small harness that
measures it instead of relying on vibes (`backend/eval/`). It ingests a labeled
fixture set (`eval/fixtures.json` — synthetic clinical documents with questions
and the gold chunk each should retrieve) and reports **recall@k** and **MRR@k**
for three modes: vector-only, lexical-only, and hybrid.

```bash
cd backend
python -m eval.run_eval
```

Example output (k=5):

```
mode          recall@k     MRR@k
--------------------------------
vector           0.750     0.408
lexical          0.833     0.625
hybrid           0.917     0.694
```

One honest caveat: the default fake embedding provider is hash-based, not
semantic, so the **vector** row above is effectively a random baseline — the table
mainly shows the lexical arm recovering exact terms and the fusion improving on
both. For real semantic numbers, set `OPENAI_API_KEY` and `USE_FAKE_PROVIDERS=false`
before running; the harness uses whatever provider is configured. `test_retrieval.py`
asserts hybrid recall never drops below vector-only, so CI guards against
regressions.

What I'd improve next: a calibrated or groundedness-based confidence score (the
current one is the average cosine of the cited chunks), and an optional
cross-encoder reranker on top of the fused candidates.

### Stack

FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · asyncpg · LangChain ·
Pinecone · PyPDF2 · OpenAI · spaCy / scispaCy (optional) ·
pydantic-settings · python-dotenv · pytest-asyncio.

### Running locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # USE_FAKE_PROVIDERS=true by default
uvicorn app.main:app --reload
```

To use the real providers, set `USE_FAKE_PROVIDERS=false` and provide
`OPENAI_API_KEY` plus `PINECONE_API_KEY` in `.env`. To enable real
scispaCy entity extraction:

```bash
pip install spacy==3.7.5
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
```

### Tests & CI

```bash
cd backend
pip install -r requirements-dev.txt
ruff check app eval tests
pytest
```

The suite in `backend/tests/` covers upload → embed → extract → query →
delete, scanned-PDF rejection, multi-turn sessions, session delete
cascading, analytics aggregation, deterministic embeddings, retry
helper, risk-flag detection, dedupe, entity extraction, and the new
retrieval pieces (BM25, RRF fusion, and the eval harness). It runs on
in-memory SQLite with the fake providers, so no Postgres, Pinecone, or
API key is needed.

GitHub Actions (`.github/workflows/ci.yml`) runs ruff + pytest on Python
3.11 and 3.12 for every push and pull request.

## Frontend

Built with Next.js 14 (App Router), Tailwind CSS, and a dark clinical
theme (slate/blue palette, JetBrains Mono accents).

Pages:

- `/` — Dashboard with document overview, **analytics panel**
  (totals, avg latency, avg confidence, per-document usage, top-5
  questions), recent queries.
- `/upload` — Drag-and-drop ingest, document type selector, live
  progress and embedding indicator (auto-triggers entity extraction).
- `/documents/[id]` — Document detail with stats and the **entity
  summary panel** (medications, diagnoses, procedures, lab values).
- `/query` — Multi-select document filter, chat history with collapsible
  source citations, latency + confidence badges, **prominent
  warning banner when `risk_flag: true`**, and a session sidebar to
  create / load / delete sessions (multi-turn aware).

Components: `TopNav`, `DocumentCard`, `ChatMessage`, `UploadZone`,
`SourceCitation`, `EntitySummaryPanel`, `AnalyticsPanel`.

### Running locally

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev          # http://localhost:3000
```

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`.

## Docker

The included `docker-compose.yml` defines three services on the
required ports:

| Service            | Port |
| ------------------ | ---- |
| `nextjs-frontend`  | 3000 |
| `fastapi-backend`  | 8000 |
| `postgresql`       | 5432 |

```bash
cp .env.example .env
docker compose up --build
```

## Notes on safety

MedQuery is grounded — answers are constructed only from retrieved
chunks, with citations rendered in the UI. The risk-flag service scans
the question, generated answer, and retrieved evidence for a fixed
list of high-risk clinical terms — `critical`, `STAT`, `emergency`,
`sepsis`, `deteriorating`, `DNR`, `code blue` — and the UI raises a
prominent warning banner whenever any are matched. The system
explicitly does **not** provide medical advice.

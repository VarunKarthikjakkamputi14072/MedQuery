# MedQuery — Clinical Document Intelligence

A full-stack RAG (retrieval augmented generation) system for clinical
documents. Upload discharge summaries, lab reports, clinical notes, and
radiology reports; MedQuery extracts text, chunks it, embeds it into a
vector store, mines medical entities, and answers grounded clinical
questions with source citations, latency / confidence tracking, and a
high-risk content banner.

## Architecture

```
Next.js 14 + Tailwind (frontend)
        │
        ▼
FastAPI backend (async)
        │
        ├──► Local filesystem (mock S3) for uploaded PDFs/TXT
        ├──► PostgreSQL (documents, sessions, queries, entities)
        ├──► LangChain RecursiveCharacterTextSplitter (512 / 50 tokens)
        ├──► spaCy / scispaCy en_core_sci_sm (+ regex fallback)  → entities
        ├──► OpenAI text-embedding-3-small (embeddings, with retries)
        ├──► Pinecone serverless index "medquery" (batched upserts ≤100)
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
| POST   | `/query`                        | Top-5 chunks (deduped by content hash), last 3 turns as context, returns answer + citations + risk   |
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

### Tests

```bash
cd backend
pytest
```

18 tests in `backend/tests/` cover upload → embed → extract → query →
delete, scanned-PDF rejection, multi-turn sessions, session delete
cascading, analytics aggregation, deterministic embeddings, retry
helper, risk-flag detection, dedupe, and entity extraction.

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

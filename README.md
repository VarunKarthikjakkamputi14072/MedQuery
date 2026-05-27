# MedQuery — Clinical Document Intelligence

A full-stack RAG (retrieval augmented generation) system for clinical
documents. Upload discharge summaries, lab reports, clinical notes, and
radiology reports; MedQuery extracts text, chunks it, embeds it into a
vector store, and answers clinical questions with grounded source
citations and risk-term flagging.

## Architecture

```
Next.js 14 + Tailwind (frontend)
        │
        ▼
FastAPI backend (async)
        │
        ├──► Local filesystem (mock S3) for uploaded PDFs/TXT
        ├──► PostgreSQL (documents, sessions, queries metadata)
        ├──► LangChain RecursiveCharacterTextSplitter (512 / 50 tokens)
        ├──► OpenAI text-embedding-3-small (embeddings)
        ├──► Pinecone serverless index "medquery" (vector store)
        └──► OpenAI gpt-4o-mini (answer synthesis with citations)
```

Both the embedding provider and the vector store have **drop-in fakes**
that activate automatically when no API key is configured
(`USE_FAKE_PROVIDERS=true` by default in `.env.example`). This means the
entire system — upload, embed, query, citations, risk flagging — works
end-to-end locally with zero external dependencies and is fully covered
by integration tests.

## Repository layout

```
backend/   FastAPI service, SQLAlchemy models, services + tests
frontend/  Next.js 14 (App Router) + Tailwind dark clinical UI
docker-compose.yml   Postgres + backend + frontend
```

## Backend

### Endpoints

| Method | Path                       | Description                                                                                          |
| ------ | -------------------------- | ---------------------------------------------------------------------------------------------------- |
| POST   | `/upload`                  | Accepts PDF/TXT (max 10 MB), stores in mock-S3 dir, extracts text, chunks via LangChain (512/50)     |
| POST   | `/embed`                   | Embeds chunks via `text-embedding-3-small`, upserts vectors into Pinecone `medquery` index           |
| POST   | `/query`                   | Retrieves top-5 chunks (Pinecone), calls `gpt-4o-mini`, returns answer + citations + risk flags      |
| GET    | `/documents`               | Lists uploaded documents with metadata                                                               |
| GET    | `/documents/{id}`          | Returns single document metadata                                                                     |
| DELETE | `/documents/{id}`          | Removes the document and its vectors                                                                 |
| GET    | `/queries`                 | Recent queries (filterable by `session_id`)                                                          |
| POST   | `/sessions`                | Create a new chat session bound to selected documents                                                |
| GET    | `/sessions/{id}`           | Fetch a session                                                                                      |
| GET    | `/health`                  | Liveness probe                                                                                       |

All endpoints are `async`. CORS is configured for the Next.js dev origin.

### Database schema (PostgreSQL via SQLAlchemy 2.0 async)

- `documents`: `id`, `filename`, `document_type`, `upload_timestamp`,
  `chunk_count`, `pinecone_ids` (JSON array), `storage_path`,
  `size_bytes`, `status`
- `sessions`: `id`, `created_at`, `document_ids` (JSON array)
- `queries`: `id`, `session_id`, `question`, `answer`,
  `retrieved_chunks` (JSON), `latency_ms`, `confidence`, `timestamp`

The same models work against SQLite (used by the test suite) and
Postgres (used in Docker / production).

### Stack

FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · asyncpg · LangChain ·
Pinecone · PyPDF2 · OpenAI · pydantic-settings · python-dotenv ·
pytest-asyncio.

### Running locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # USE_FAKE_PROVIDERS=true by default
uvicorn app.main:app --reload
```

To use the real providers, set `USE_FAKE_PROVIDERS=false` and provide
`OPENAI_API_KEY` plus `PINECONE_API_KEY` in `.env`.

### Tests

```bash
cd backend
pytest
```

The suite (`tests/test_documents.py`, `tests/test_services.py`)
exercises upload → embed → query → delete, session reuse, validation
errors, and the chunking + risk-flag services.

## Frontend

Built with Next.js 14 (App Router), Tailwind CSS, and a dark clinical
theme (slate/blue palette, JetBrains Mono accents).

Pages:

- `/` — Dashboard with document overview, recent queries, quick stats.
- `/upload` — Drag-and-drop ingest, document type selector, live
  progress and embedding indicator.
- `/query` — Multi-select document filter, chat history with collapsible
  source citations, latency + confidence badges, risk-term flags.

Components: `DocumentCard`, `ChatMessage`, `UploadZone`,
`SourceCitation`, `TopNav`.

### Running locally

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev          # http://localhost:3000
```

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`.

## Docker

The included `docker-compose.yml` spins up Postgres, the FastAPI
backend, and the Next.js frontend:

```bash
docker compose up --build
```

## Notes on safety

MedQuery is grounded — answers are constructed only from retrieved
chunks, with citations rendered in the UI. The risk-flag service
highlights critical clinical terms (e.g. *sepsis*, *hypoxia*,
*hemorrhage*, *DKA*) anywhere they appear in the question, answer, or
retrieved evidence. The system explicitly does **not** provide medical
advice.

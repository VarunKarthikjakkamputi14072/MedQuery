# Deploying MedQuery

The demo runs entirely on deterministic fakes (`USE_FAKE_PROVIDERS=true`) over
SQLite, so it deploys with **no API keys and no managed database** — zero cost.

Topology: **backend on Render**, **frontend on Vercel**.

## 1. Backend — Render

1. In the Render dashboard: **New + → Blueprint**, connect this repo. Render reads
   [`render.yaml`](./render.yaml) and provisions the `medquery-backend` web service
   (Docker, free plan, health check at `/health`).
2. Deploy. Note the public URL, e.g. `https://medquery-backend-xxxx.onrender.com`.
3. After the frontend is live (step 2), set the `CORS_ORIGINS` env var on the service
   to the Vercel URL and redeploy.

The Dockerfile binds `$PORT` (injected by Render); locally it defaults to 8000.

## 2. Frontend — Vercel

From the `frontend/` directory (root directory = `frontend`):

```bash
cd frontend
vercel link                                   # once, to create the project
vercel env add NEXT_PUBLIC_API_URL production  # paste the Render backend URL
vercel --prod
```

`NEXT_PUBLIC_API_URL` is read at build time (`src/lib/api.ts`), so it must be set
before `vercel --prod`. Re-deploy if you change it.

## 3. Wire CORS

Set `CORS_ORIGINS` on the Render backend to the production Vercel URL
(e.g. `https://medquery.vercel.app`) and redeploy so the browser can call the API.

## Going beyond the demo (real inference)

Providers auto-detect from whichever keys are present — no all-or-nothing flag:

| You set | Result |
| --- | --- |
| nothing | deterministic fakes (the zero-cost demo) |
| `OPENAI_API_KEY` | **real GPT-4o-mini + embeddings** — actually reads citations and writes conversational answers; vector search uses the built-in in-memory store |
| `OPENAI_API_KEY` + `PINECONE_API_KEY` | as above, but backed by a real Pinecone index |

So to turn on the real "brain", just set `OPENAI_API_KEY` on the Render service —
**Pinecone is optional.** (If the service still has `USE_FAKE_PROVIDERS=true` from the
demo, remove it or set it to `false`; that flag force-pins the fakes on.)

`GET /health` reports the active backend per provider, e.g.
`{"providers": {"embeddings": "openai", "llm": "openai", "vector_store": "in-memory"}}`.

For persistence across redeploys, also set a Postgres `DATABASE_URL`.

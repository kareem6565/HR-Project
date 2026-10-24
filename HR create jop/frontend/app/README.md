# AI HR Assistant — Minimal Test Frontend

A minimal React + Vite frontend for **manual UX testing** against the FastAPI
backend. It talks to the real `/api/v1` endpoints (no mock data) and uses the
backend's header-based identity model.

## Prerequisites

1. PostgreSQL running: `docker compose up -d postgres` (from repository root).
2. Backend running: `uvicorn app.main:app --reload` (from `backend/`, port 8000).
   CORS is enabled for `http://localhost:5173` / `http://127.0.0.1:5173`.

## Setup

```bash
cd frontend/app
npm install
copy .env.example .env
```

Edit `.env` and set demo identity:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_ORG_ID=<a real organization id (UUID)>
VITE_USER_ID=<an active user id (UUID) that belongs to that org>
```

The backend has no login — it trusts `X-Organization-Id` / `X-User-Id` headers,
so paste actual IDs that exist in your database.

## Run

```bash
npm run dev      # http://localhost:5173
npm run build    # production build -> dist/
```

## What it exercises

- **Health** — `GET /api/v1/health` (connectivity check).
- **Jobs** — `POST /api/v1/jobs` and `GET /api/v1/jobs/{id}` (create/lookup).
- **Candidate Pool** — `GET /api/v1/jobs/{id}/candidates` (Phase 4.5 ranked,
  grouped candidates for a job).

To see a populated candidate pool, the job must have applications with current
evaluations (populate via the existing API/workflows or seed data).

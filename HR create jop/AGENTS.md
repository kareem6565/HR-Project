# AGENTS.md

Repository for the AI HR Recruitment Assistant. Candidate review loop is
implemented end-to-end; the local backend currently runs the **real Soal AI
provider** (`AI_PROVIDER=soal` in `backend/.env`, gateway `soal.help`, model
`gemini-3.5-flash`) — `FakeAIProvider` remains the deterministic code default
when `AI_PROVIDER` is unset. Work is in `backend/` and `frontend/frontend_last/`.
See [`docs/roadmap.md`](docs/roadmap.md) for phase status. This is a
**pre-production MVP**: no production auth and no Docker app deployment yet.
The HERA chat/matching, interviews, interview questions, and AI-activity
observability features are implemented against real backend endpoints.

## Process rules (required reading)

Read `docs/development-rules.md` and follow it. It mandates
`PLAN -> APPROVAL -> IMPLEMENT -> TEST -> REVIEW -> COMMIT`, forbids writing code
before approval, forbids touching unrelated files, and forbids new
frameworks/architecture without approval. `docs/architecture.md` documents
intended design decisions that are intentionally not yet finalized (LLM
provider, LangGraph wiring). Do not implement those without explicit
instruction.

## Command rules

- Backend commands run from **`backend/`**.
- Frontend commands run from **`frontend/frontend_last/`** (the only
  canonical frontend; the legacy `frontend/frontend3/` build base was retired at
  the release checkpoint, and `frontend/app` plus any other `frontend/` folder
  are not the canonical app).
- Never wire or run `n8n_workflow.json` and never treat `docs/HERA_system_flow.html`
  as runtime architecture — both are legacy/reference artifacts.

## Backend commands (run from `backend/`)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                 # needs Postgres running (see below)
ruff check .
ruff format --check .
alembic upgrade head   # after Postgres is up
uvicorn app.main:app --reload
```

Lint uses ruff with `E F I UP B` rules, line length 100, double quotes
(`pyproject.toml`).

## Frontend commands (run from `frontend/frontend_last/`)

```bash
npm install
npm run dev            # dev server (Vite)
npm run lint           # oxlint
npm run build          # production build
```

## Database and test gotchas

- Start Postgres first: `docker compose up -d postgres` from repo root (image
  `postgres:16-alpine`, creds `hr_ai_assistant`/`hr_ai_assistant`, port 5432).
  That compose file is the local dev DB only — it is not the app's Docker
  deployment.
- Config is loaded from `backend/.env` via `app/core/config.py`
  (pydantic-settings). Copy `backend/.env.example` to `backend/.env` if absent.
  Defaults already match the compose DB, so it usually runs with no env file.
- `DATABASE_URL` is the app DB; **`TEST_DATABASE_URL` is a separate DB**
  (`..._test`). Tests DO NOT use `TEST_DATABASE_URL` directly against your data
  — `tests/conftest.py` auto-creates the test DB if missing and drops/recreates
  all tables per session. Keep the two URLs pointing at different databases; a
  test run will wipe the DB named in `TEST_DATABASE_URL`.
- `tests/conftest.py` imports `from app import models` so all models register on
  `Base.metadata`. When you add a model, keep it imported into
  `app/models/__init__.py`.
- Alembic `env.py` pulls connection from `settings.database_url` and
  autogenerates against `Base.metadata`. **Revision IDs must stay under 32
  chars** (the `alembic_version.version_num` column width). Current head:
  `011_chat`.

## Operational runbook (Windows / this machine)

On this machine `python` is not on PATH and npm needs a ComSpec fix, so prefer
the helper scripts in `tools/` over raw commands:

```powershell
tools\start_backend.ps1                          # postgres not included; backend on :8000
tools\start_frontend.ps1                         # frontend_last Vite on :5174
tools\start_frontend.ps1 5174 http://localhost:8000/api/v1   # dev against local backend
tools\run_tests.ps1                              # pytest -m "not soal"
tools\run_gemini_tests.ps1                       # live soal.help provider tests
backend\.venv\Scripts\python.exe tools\e2e_screening_flow.py   # live E2E (needs backend up)
```

- `start_backend.ps1` strips any inherited `SOAL_API_KEY` before launching so
  `backend/.env` is always authoritative. **Do not create a user/global
  `SOAL_API_KEY` environment variable** — pydantic-settings gives env vars
  precedence over `.env`, and a stale one previously shadowed the working key
  (soal.help rejects it with a 401).
- Backend logs: `%TEMP%\opencode\backend.log` / `backend.err.log`; frontend:
  `%TEMP%\opencode\frontend_last.log`.
- Ports: FastAPI `:8000`; frontend_last dev `:5174`; Postgres `:5432` via
  `docker compose up -d postgres` (tests need it; the test DB is created fresh
  per run). CORS already allows 5173/5174/5175 + localhost:8000 (`backend/.env`).
- Frontend API base defaults to `https://soal.help/api/v1`; override with
  `VITE_API_BASE_URL` (e.g. `http://localhost:8000/api/v1`) for local work.
- E2E scores vary run to run with the live LLM; the harness only asserts
  relative sanity (> 0), not exact numbers.

## Layout

- `backend/app/` — FastAPI app. Entrypoint `app/main.py` (`create_app()`),
  router at `app/api/v1/router.py`, settings `app/core/config.py`, engine
  `app/core/database.py`.
- `backend/app/models/` — SQLAlchemy ORM models; Pydantic schemas live under
  `backend/app/api/v1/schemas/` (the top-level `backend/app/schemas/` package is
  an empty placeholder to be removed later). `backend/app/services/` holds
  business logic; `backend/app/repositories/` is an empty placeholder to be
  removed later.
- `backend/alembic/versions/` — numbered migrations (`00x_*.py`).
- `frontend/frontend_last/` — canonical React/Vite frontend (pages, services,
  components). Zero mock data; every page calls the live backend or shows an
  honest empty/error state.
- `frontend/frontend3/` — retired build base `frontend_last` was copied from
  (removed at the release checkpoint).
- `frontend/app/` — minimal manual-test frontend (not the canonical app).
- `backend/storage/` — runtime-generated uploads (uploaded CVs); ignored by git,
  not source.
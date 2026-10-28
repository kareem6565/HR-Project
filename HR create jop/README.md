# HERA — AI-assisted recruitment and employee lifecycle

HERA helps HR teams manage jobs, CV screening, candidate evidence, interviews,
and hiring workflows. AI can extract information and propose evidence; approved
backend rules calculate match scores, and a human recruiter remains responsible
for every hiring decision.

## Project status

| Capability | Status | Notes |
| --- | --- | --- |
| Authentication and role-aware access | Implemented | Local login, token handling, admin/recruiter roles, organization scoping. |
| Job management | Implemented | Create/edit jobs, extract and review structured job profiles, approval workflow, and source-grounded job-profile quality notes. |
| CV intake and screening | Implemented | PDF/DOCX upload, asynchronous batches, text extraction, candidate profiles, evidence verification, deterministic score, retryable item failures, and review links. |
| Screening progress | Implemented | The UI polls the batch API automatically and reports progress from terminal item counts; no simulated per-file progress. |
| Candidate review and HR decisions | Implemented | Requirement-level evidence and limitations are shown separately from human Advance/Hold/Reject decisions. |
| Candidate pool and matching | Implemented | Job-scoped matching results and comparison for candidates evaluated against the same job; internal talent pool search uses stored profile skills. |
| Interviews | Implemented | Scheduling, availability/conflict handling, generated question sets with review guides, and interviewer feedback. External calendar synchronization is not included. |
| Dashboard and analytics | Implemented | Operational overview and reporting use backend data; definitions and filters depend on the selected view. |
| HERA assistant chat | Implemented | Conversational recruitment support uses the existing authorized backend workflow; it does not make hiring decisions. |
| AI activity and audit history | Implemented | Workflow traces, provider activity, and audit records are available to authorized users. |
| Candidate-facing portal | Partial | Invitation-related API support exists; this is not a complete self-service career site. |
| Employee onboarding/lifecycle | Not implemented | Post-hire employee records, onboarding tasks, and lifecycle administration remain future work. |
| LinkedIn sourcing, external ATS, email/calendar sync | Not implemented | Requires approved integrations, permissions, and product decisions. HERA does not scrape LinkedIn. |
| Candidate communication drafts and cross-job rediscovery | Planned | Do not assume automated messaging or broad rediscovery is available. |

The implementation is an evolving pre-production MVP. See
[`docs/roadmap.md`](docs/roadmap.md) for phase status and
[`docs/development-rules.md`](docs/development-rules.md) for the required
PLAN → APPROVAL → IMPLEMENT → TEST → REVIEW → COMMIT workflow.

## How CV screening works

1. An authorized recruiter selects a job with an approved job profile and uploads PDF/DOCX CVs.
2. The API stores the files and creates a screening batch. The backend worker, enabled by default, claims queued items and processes them independently.
3. The configured AI provider extracts a candidate profile and proposes requirement-level evidence. Positive evidence is checked against the extracted source text using exact-quote verification.
4. Backend scoring applies the existing approved requirement weights and evidence values. The model does not choose the score or the HR decision.
5. The frontend polls batch status every two seconds while items remain queued or running. It updates the progress bar and per-file status from the API response; completed items show their score and a direct review action without requiring a page refresh.

The progress percentage is `(done + failed + duplicate + cancelled) / total files`.
It reflects files that reached a final state, not a model's internal token-level
progress. Failed items are reported separately and can be retried when allowed.
If the UI remains queued, check that the backend is running, `ENABLE_SCREENING_WORKER`
is not disabled, the database is reachable, and backend logs show the worker
started. A progress bar cannot make a stopped worker process a queue.

## Requirements

- Python 3.11 or newer.
- Node.js and npm supported by the installed Vite toolchain.
- PostgreSQL 16 for normal local development and the backend test suite.
- Docker Desktop / Docker Engine for the Postgres service or full Compose setup.
- For real AI screening: an authorized Ollama Cloud API key. Fake provider mode is available for offline deterministic development and tests.

## Quick start — Windows PowerShell

From the repository root:

```powershell
docker compose up -d postgres
Copy-Item backend\.env.example backend\.env
python -m venv backend\.venv
```

Edit `backend\.env` before starting the backend:

- Set a private, high-entropy `JWT_SECRET_KEY` of at least 32 characters.
- For the configured Ollama Cloud model, set `AI_PROVIDER=ollama`, add `OLLAMA_API_KEY`, and keep or change `OLLAMA_BASE_URL` and `OLLAMA_MODEL` as needed.
- Keep `DATABASE_URL` pointed at the local `hr_ai_assistant` database. Do not point test configuration at it.

Start the backend in its own PowerShell window:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The worker starts in the backend process unless `ENABLE_SCREENING_WORKER=false`.

Start the frontend in another PowerShell window:

```powershell
Set-Location frontend\frontend_last
Copy-Item .env.example .env
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

Open <http://127.0.0.1:5174>. API docs are at <http://127.0.0.1:8000/docs>;
the health endpoint is <http://127.0.0.1:8000/api/v1/health>.

### Admin account

Create an administrator through the supported CLI after migrations have run.
The command prompts for a password without printing it:

```powershell
Set-Location backend
hera-admin --org-name "Your Organization" --email "admin@example.com" --full-name "HERA Admin"
```

Use a separate, authorized recruiter account for HR workflow checks. Do not put
passwords or tokens in source control, shell history, screenshots, or logs.

## Full stack with Docker Compose

The Compose stack runs PostgreSQL, the FastAPI application (including its
screening worker), and the canonical frontend:

```powershell
Copy-Item .env.example .env
# Edit .env and set a strong JWT_SECRET_KEY before exposing the app.
docker compose up --build -d
```

Open <http://localhost:8080> and <http://localhost:8000/docs>. Compose defaults
to `AI_PROVIDER=fake` so it can run without cloud credentials. To use Ollama,
set `AI_PROVIDER=ollama` and `OLLAMA_API_KEY` in the root `.env`; Compose passes
the provider settings to the backend. Never commit either `.env` file.

## Configuration

Backend settings are loaded from `backend/.env` for local runs. In Compose,
settings are supplied by the root `.env` and `docker-compose.yml`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Application PostgreSQL connection. |
| `TEST_DATABASE_URL` | Separate disposable test database; test setup recreates its tables. |
| `STORAGE_ROOT_DIR` | Backend file storage root (default: `backend/storage`). |
| `AI_PROVIDER` | `ollama`, `soal`, or `fake`. |
| `OLLAMA_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Ollama Cloud access and model; default model is `gemma4:31b`. |
| `SOAL_API_KEY`, `SOAL_BASE_URL`, `SOAL_MODEL` | Optional Soal-compatible provider configuration. |
| `JWT_SECRET_KEY` | Required signing secret; use a unique high-entropy value outside tests. |
| `ENABLE_SCREENING_WORKER` | Enables the embedded batch worker; defaults to `true`. |
| `VITE_API_BASE_URL` | Frontend API base, including `/api/v1`; local proxy default is `/api/v1`. |

The frontend only uses `VITE_*` variables. AI credentials belong on the backend
and must never be prefixed with `VITE_`.

## Tests and quality checks

Frontend, from `frontend/frontend_last/`:

```powershell
npm test
npm run lint
npm run build
```

Backend, from `backend/`:

```powershell
pytest -m "not soal" -q
ruff check .
ruff format --check .
```

Backend tests use `TEST_DATABASE_URL` and recreate the tables in that database.
Before testing, verify it names a disposable database distinct from
`DATABASE_URL`; never run the suite against development or production data.
Live provider and Ollama quality evaluations are opt-in and should use synthetic
CVs only. Ordinary pytest must not make live model calls.

## Repository layout

- `backend/` — FastAPI routes, services, AI provider/workflows, worker, models, migrations, and tests.
- `frontend/frontend_last/` — canonical React/Vite application.
- `tools/` — Windows runbooks, synthetic quality runners, and screening validation utilities.
- `docs/` — architecture, product requirements, development rules, design direction, and roadmap.
- `backend/storage/` — runtime upload storage; never commit generated candidate files.

`frontend/app` is a manual-test harness; it is not the canonical frontend.
`n8n_workflow.json` and `docs/HERA_system_flow.html` are legacy/reference
artifacts and are not runtime architecture.

## Security and data handling

- Never commit `.env`, API keys, passwords, JWTs, local databases, uploaded CVs, or provider responses containing private data.
- Use synthetic CVs for provider testing. Do not send candidate data to a provider unless the organization has authorized that processing.
- CV text is untrusted input. AI output is validated, positive evidence must quote source text, and hiring decisions remain under human control.
- Keep `DATABASE_URL` and `TEST_DATABASE_URL` separate. The test database is disposable.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).

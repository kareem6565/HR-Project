# Recruitment AI Service

FastAPI service responsible for CV processing, embeddings, candidate
matching support, and AI explanation for the AI-assisted recruitment
platform. Consumed internally by the ASP.NET Core API — never exposed
directly to end users, never touches the database.

## Architecture

ASP.NET Core -> FastAPI -> LangGraph orchestrator -> 3 agents
(Extraction, Evaluation, Explanation) -> LLM provider (Ollama dev /
Gemini prod). Every request is tagged to an organization via the
`X-Organization-Id` header (multi-tenant isolation) and every workflow
step is recorded in an `AI trace` for observability and debugging.

The Evaluation agent NEVER calls an LLM — scoring is 100% deterministic
Python, versioned (`SCORING_VERSION` in `app/models/job.py`).

## Stack
- Python 3.11+
- FastAPI + Pydantic
- LangGraph (multi-agent orchestration) + LangChain
- Ollama (dev) / Gemini (prod) — swappable via `LLM_PROVIDER`

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn main:app --reload --port 8000
```

Docs: http://localhost:8000/docs

**Every endpoint below requires the header `X-Organization-Id: <any-string>`**
(multi-tenant isolation — enforced even in dev).

## API Contract (for Person 2 / ASP.NET integration)

All endpoints are versioned implicitly under `/internal/ai/*` — a `/v2/`
prefix will be added if a breaking change is ever needed.

### `POST /internal/ai/extract-cv`
Raw CV text -> structured `CandidateExtraction`. See Week 1 section below.

### `POST /internal/ai/job-profile`
Raw job description text -> structured `JobProfile`.
```json
// Request
{ "job_text": "We need a Python developer with 3+ years..." }

// Response
{
  "job_profile": {
    "title": "Python Developer",
    "must_have": {"skills": ["Python"], "min_experience_years": 3, "education": [], "responsibilities": []},
    "important": {"skills": ["SQL"], "min_experience_years": null, "education": [], "responsibilities": []},
    "nice_to_have": {"skills": ["Docker"], "min_experience_years": null, "education": [], "responsibilities": []}
  }
}
```

### `POST /internal/ai/candidate-profile`
Raw CV text -> `CandidateExtraction` + version number. Keeps previous
versions in memory, keyed by `candidate_key` (defaults to extracted email).
```json
// Request
{ "cv_text": "...", "candidate_key": "jane@example.com" }

// Response
{ "profile": {...}, "version": 2, "candidate_key": "jane@example.com", "created_at": "..." }
```

### `GET /internal/ai/candidate-profile/{candidate_key}/history`
Returns every stored version for a candidate within the calling organization.

### `POST /internal/ai/evaluation`
Pure deterministic evaluation — no LLM call. `CandidateExtraction` +
`JobProfile` -> `MatchEvidence` with a full `ScoreBreakdown`.

### `POST /internal/ai/explanation`
Score + evidence -> human-readable explanation (LLM call, but the LLM
never changes the score).

### `POST /internal/ai/evaluate-candidate`
The full pipeline in one call: CV text + JobProfile -> extraction ->
evaluation -> explanation, run through the LangGraph orchestrator.
Returns `candidate`, `evidence` (with `breakdown`), `explanation`, and
`trace` (every step's status/duration, or exactly where it failed).

### Error format (all endpoints)
| Status | Meaning |
|---|---|
| 400 | Missing/invalid input, or missing `X-Organization-Id` header |
| 422 | LLM output failed validation after retries, or workflow step failed |
| 503 | LLM provider unavailable (timeout, connection error) |
| 500 | Unexpected internal error (never leaks stack traces) |

## Architecture rules (do not violate)
- The AI service is stateless-ish and **never** touches SQL Server directly.
  (Candidate profile versioning is in-memory today — a placeholder until
  Person 2's database owns durable storage.)
- The LLM never sees raw binary files — only extracted text.
- CV / job-description / any external text is **untrusted data**.
- The LLM never computes the final match score — `EvaluationAgent`
  contains zero LLM calls, ever.
- Every request is isolated by `X-Organization-Id`.

## Testing
```bash
pytest
```

## Roadmap
- **Done:** CV extraction, JobProfile builder, CandidateProfile +
  versioning, deterministic scoring + breakdown, explanation, LangGraph
  multi-agent orchestration, AI tracing, multi-tenant isolation.
- **Week 2:** real PDF/DOCX file upload, ranking/filtering/search,
  full security review, comprehensive test suite, RAG (optional).


# HERA — System Architecture & LangGraph Roadmap

Scope: the `hr-ai-assistant` monorepo. Backend is FastAPI (Python), frontend is
React/Vite (`frontend/frontend3/sandbox`). This document describes the **current**
architecture as-built and then assesses **where LangGraph would be introduced**
and **why** — it is a roadmap, not a code change. No dependencies were added.

---

## 1. High-level system

```
                        ┌──────────────────────────────────────────────┐
                        │               Web Browser                     │
                        │  HERA React SPA (frontend/frontend3/sandbox)  │
                        │  services/*.js → apiClient (Axios)            │
                        └───────────────┬──────────────────────────────┘
                                        │ HTTP (JSON)
                                        │ header identity:
                                        │   X-Organization-Id
                                        │   X-User-Id
                                        ▼
                        ┌──────────────────────────────────────────────┐
                        │              FastAPI app (backend)          │
                        │  app/main.py · CORS · /api/v1 router        │
                        │  routes/  (jobs, candidates, candidate_pool,│
                        │           evaluations, job_applications,    │
                        │           profiles, resumes, orgs, users,   │
                        │           workflows, hr_decisions, health)  │
                        └───────┬──────────────┬──────────┬───────────┘
                                │              │          │
                    HTTP 8000   │              │          │
                                ▼              ▼          ▼
            ┌──────────────────────┐  ┌────────────┐  ┌──────────────┐
            │  app.services        │  │    AI      │  │  sync worker │
            │  job_service,        │  │  stage     │  │  (workflows) │
            │  candidate_pool_service, etc.        │  │              │
            │                      │  └──────┬─────┘  └──────────────┘
            └──────────┬───────────┘         │
                       ▼                     ▼
            ┌──────────────────────┐  ┌──────────────────────────┐
            │  PostgreSQL          │  │  AI providers             │
            │  (docker compose,    │  │  app/ai/providers/*       │
            │   port 5432)         │  │  - base.py  (AIProvider)  │
            │  SQLAlchemy models   │  │  - fake.py  (deterministic)│
            └──────────────────────┘  └──────────────────────────┘
```

Processing is synchronous today: a request reaches a route → a service validates
and persists → (for AI flows) a workflow calls the `AIProvider` and stores
versioned artifacts + full trace rows. There is **no queue/broker, no worker
pool, and no LangChain/LangGraph** in the stack.

---

## 2. Backend layers

| Layer | Path | Responsibility |
|---|---|---|
| API/transport | `app/api/v1/routes/*.py` | HTTP → service/workflow; header-based identity (`X-Organization-Id`, `X-User-Id`); Pydantic request/response schemas |
| Orchestration | `app/ai/workflows/*.py` | Deterministic, single-run pipelines (profile extraction, candidate evaluation). Plain Python classes, no graph runtime |
| Domain services | `app/services/*.py` | Reads/writes, scoring, candidate-pool grouping, trace bookkeeping |
| AI contracts | `app/ai/contracts/*.py` | Pydantic output contracts + validators, hash refs, schema versioning |
| AI providers | `app/ai/providers/*.py` | Provider-agnostic `AIProvider` interface; deterministic `FakeAIProvider` |
| Persistence | `app/models/*.py`, `alembic/` | SQLAlchemy models + migrations on PostgreSQL |
| Config | `app/core/config.py` | Settings (CORS origins, etc.) |

Key facts verified:
- Orchestration is **hand-written imperative Python** — e.g.
  `CandidateEvaluationWorkflow.run()` (`app/ai/workflows/candidate_evaluation.py:104`)
  runs a linear pipeline: load application → resolve approved `JobProfile` +
  current `CandidateProfile` → run **evidence** AI component → run **explanation**
  AI component → deterministic scoring → persist new versioned `CandidateEvaluation`
  + `MatchEvidence` → record workflow/step/AI traces. The caller owns the
  transaction (workflows never commit).
- The **only** provider today is `FakeAIProvider`; real provider adapters are
  explicitly deferred per the package docstrings.
- Scoring is deterministic (Phase 4.2); candidate grouping is deterministic
  (Phase 4.5: `MUST_REVIEW_MIN=70`, `CONSIDER_MIN=40` in
  `app/services/candidate_pool_service.py`). The LLM never produces a score.

---

## 3. LangGraph status (as of this document)

**LangGraph is not built and not installed.** It is not in `pyproject.toml`
dependencies, and there is no `langchain`/`langgraph` import anywhere in the
backend. The workflow package docstring explicitly marks
"real provider adapters, LangChain/LangGraph/agents, and workers" as
**out of scope**. The frontend also calls external **n8n webhooks** for CV
screening and interview scheduling (outside this backend).

The design already leaves the exact seam where LangGraph would be added: the
`AIProvider` interface. Nothing in the providers, contracts, services, or
database depends on the orchestration runtime, so a LangGraph graph could be
introduced as an *alternative* orchestrator for each workflow without touching
the contracts or the storage layer.

---

## 4. Where LangGraph *could* be used (and where it should NOT be)

### 4.1 Good fits (introduce here, in priority order)

1. **Candidate evaluation as a `StateGraph`** (`app/ai/workflows/candidate_evaluation.py`).
   Currently a rigid 4-step sequence. A LangGraph `StateGraph` would model:
   `load_and_validate → generate_evidence → generate_explanation → score → persist → trace`,
   with **conditional edges** for retry-on-validation-failure, provider
   fallback, or parallel evidence/explanation nodes later. This is the single
   highest-value target because it is the core "agent" flow.

2. **Profile extraction** (`job_profile_extraction.py`, `candidate_profile_extraction.py`)
   — same pattern; easy to migrate once #1 is proven.

3. **Future multi-step / multi-agent screening pipeline** — e.g. a graph that
   chains resume parse → candidate profile → evaluate → HR decision → interview
   scheduling. This is where LangGraph's explicit cycles and human-in-the-loop
   (interrupt / checkpointer for HR approval) become genuinely useful.

4. **Human-in-the-loop gates**: LangGraph checkpoints would let a workflow
   *pause* when an `HRDecision` is required, resume after HR acts, and be
   resumable with persisted state — replacing the current "requery for latest
   decision" approach.

### 4.2 Where LangGraph should NOT be used

- **Deterministic scoring / grouping** (Phases 4.2, 4.5). No LLM, no branching —
  keep as plain functions.
- **Simple CRUD routes / services**. Adding a graph runtime here adds
  complexity for linear work.
- **Externally-scheduled n8n flows**. Keep those in n8n.

---

## 5. Roadmap (incremental, no disruption to the current deterministic path)

| # | Step | Deliverable | Why |
|---|---|---|---|
| R0 | Add `langgraph` (+ `langchain-core` for messages) to `pyproject.toml` | dependency | enable the runtime |
| R1 | Build an `EvaluationGraph` as a **new** module beside the existing class (e.g. `app/ai/workflows/candidate_evaluation_langgraph.py`) | a runnable `StateGraph` mirroring the current 4-step pipeline, using the same `AIProvider`, contracts, and trace calls | prove parity before any switchover |
| R2 | Keep current `CandidateEvaluationWorkflow` as the default; add a config toggle `AI_ORCHESTRATOR={classic,langgraph}` | controlled rollout | A/B without risk |
| R3 | Add provider fallback + retry with conditional edges in the graph | resilience | graph value over imperative code |
| R4 | Add a human-in-the-loop `HR_DECISION` node with checkpointer | pause/resume on HR action | flagship LangGraph advantage |
| R5 | (Later) orchestrate screening sequence (resume → profile → evaluate → decide) as one graph with parallelism | end-to-end agent pipeline | where the framework pays off most |

---

## 6. Tradeoffs

**Adopting LangGraph**
+ Native state graph + conditional/parallel edges; resilient retry/fallback.
+ Checkpointing enables durable human-in-the-loop (resume mid-pipeline).
+ Observable/traceable execution; the existing `WorkflowTraceService` can map
  graph steps to trace rows.
− New runtime dependency and learning surface on top of an already-working,
  well-tested deterministic path.
− Adds a graph indirection for what are mostly linear pipelines today.
− Overkill unless we actually need branching/retries/parallelism or HITL —
  which is exactly why the roadmap starts with a **parity** build and a toggle.

**Keeping plain Python (status quo)**
+ Simple, explicit, trivially testable, low deps.
− Manual control flow; retries/fallbacks/parallelism and durable HITL must be
  hand-rolled.

**Recommendation:** do not replace anything yet. Add LangGraph behind the R0–R3
toggle only when the requirements (retries, branching, parallelism, or durable
human-in-the-loop HR decisions) actually arrive. The `AIProvider` seam means the
decision is reversible and low-cost.

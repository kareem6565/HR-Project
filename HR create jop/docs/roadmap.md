# HERA roadmap and implementation status

This roadmap reflects the current code paths and tests in the canonical
repository (`backend/` and `frontend/frontend_last/`). A route or component by
itself does not mean a capability is complete; status includes workflow,
validation, and user-facing behavior. Recheck status as implementation changes.

## Current product status

| Area | Status | Current implementation | Remaining work |
| --- | --- | --- | --- |
| Authentication and access control | Implemented for the MVP | Login, session/token handling, role-aware frontend routes, backend organization scoping, and admin bootstrap CLI. | Production identity provider, deployment security review, operational session policies. |
| Jobs and job profiles | Implemented | Job CRUD, AI-assisted extraction into a structured profile, HR review/approval, and source-backed quality notes. | Further job quality analysis should remain advisory and must not invent requirements. |
| CV ingestion and screening | Implemented | PDF/DOCX batch upload, worker processing, profile extraction, evidence generation and exact-source quote verification, deterministic scoring, retryable errors, and review links. | Continue provider-quality regression testing and monitor failure/latency behavior before production adoption. |
| Candidate review and HR decisions | Implemented | Application evidence, AI review category, processing state, and human Advance/Hold/Reject decision are separate. | Product-specific audit and retention policies. |
| Candidate search and comparison | Implemented | Candidate lists, job-scoped matching, same-job comparison, and internal talent-pool search based on stored profile skills. | Broader cross-job rediscovery requires product approval, retention rules, and purpose/consent review. |
| Interviews | Implemented | Scheduling, availability/conflict checks, candidate question sets with review guidance, and interviewer feedback. | External calendar synchronization and interview transcription are not implemented. |
| Dashboard and analytics | Implemented | Separate operational dashboard and analytics/reporting views backed by the API. | Add deeper exports/filters only where metric definitions and API support are clear. |
| AI activity, traces, and audit | Implemented | Workflow activity and audit records are available through authorized routes and UI. | Production monitoring/alerting integration and operational retention policy. |
| Candidate portal | Partial | Invitation and portal API foundations exist. | Complete candidate self-service experience and lifecycle coverage. |
| Employee lifecycle and onboarding | Not implemented | No complete employee record, onboarding task workflow, or post-hire lifecycle UI. | Define scope and data model before implementation. |
| Candidate communications | Not implemented | No complete HR-reviewed message drafting and delivery workflow. | Add reviewed drafts only after product approval; sending must be human-authorized. |
| External sourcing and integrations | Not implemented | No LinkedIn scraping or external ATS/calendar/mail synchronization. | Use only official, permissioned integrations; never scrape LinkedIn. |

## AI and decision boundaries

- AI providers extract or propose structured information and evidence. Provider
  output is validated before use.
- Positive requirement matches require evidence that passes exact-source quote
  verification.
- The backend scoring formula and approved requirement weights are authoritative;
  do not change them to make scores appear more favorable.
- A recruiter remains responsible for hiring decisions. AI categories and
  processing failures must not be presented as HR decisions.
- `fake` is intended for deterministic offline development/tests;
  `ollama` and `soal` make provider requests when configured.
- Live model-quality checks use synthetic CV data and are opt-in. Ordinary
  pytest must not make live provider calls.

## Near-term priorities

1. Keep the asynchronous screening worker and frontend batch progress observable
   and truthful. The UI progress percentage is derived from API item counts; it
   is not estimated model progress.
2. Maintain synthetic regressions for evidence extraction, exact quotes, scoring,
   persistence, and provider response variation.
3. Improve error visibility and production readiness without changing scoring or
   reducing human review.
4. Define onboarding, communication, and external integration requirements
   before adding new schemas, endpoints, or providers.

## Reference-only artifacts

- `n8n_workflow.json` is a legacy workflow sketch; do not run or wire it into
  HERA.
- `docs/HERA_system_flow.html` is a reference illustration, not runtime
  architecture.
- `frontend/frontend_last/` is the canonical application. `frontend/app` is a
  manual-test harness, not the product frontend.

# Agent Progress

## CURRENT
- Task: A5 [GATE] plan posted; waiting for approval of proposed top N and below-N behavior. Do not implement before approval.
- Branch: `agent/recruitment-work` (created from the existing `feat/public-candidate-application` tree).
- Housekeeping commits: `6bdf7a5` frontend readability; `8f14d0a` HERA brand mark; `167a4f1` HR Manager workspace/branding; `b827907` startup helper; `a35b6ab` change log.
- S8 plan: (1) use the repository root `.github/workflows` and canonical backend/frontend; (2) add one CI workflow for Gitleaks, pip-audit, npm audit (high+), Ruff, pytest, Vitest, and build; (3) document exact local commands here; (4) validate workflow structure and record limitations. No secrets, dependencies, application changes, or data migrations planned.
- Baseline plan executed: (1) preserve existing local edits; (2) run backend lint, format, and non-Soal pytest; (3) run frontend lint, tests, and build; (4) isolate the reported JobDetails failures; (5) record summaries. T0.2 is now complete.
- T0.3 plan was approved and completed: audit references; delete unused identity UI and evaluations redirect component; replace legacy URLs with query/hash-preserving redirects; point dashboard actions and review navigation at canonical routes; update focused route tests; run frontend validation; commit only task files.
- S1 audit and implementation plan approved. Preserve the seeded developer/test accounts and their existing development-only password for `APP_ENV=development`; outside development require explicit `HR_SEED_PASSWORD`, validate it with the existing password policy, and reject the known weak value. Never print a password. Implementation scope: (1) update `tools/seed_hr_manager.py` with the environment guard, password policy, account must-change flag, generic output, and tests; (2) update `tools/setup_local.ps1` to pass its configured `APP_ENV` and remove credential output; (3) add `must_change_password` via Alembic, add a self-service password-change page and request gating in `HR manager/includes/auth.php`; (4) enforce the flag in `HR manager/login.php`, clear it after a successful change, and mark admin-reset passwords for change in `HR manager/api/employees.php`; (5) remove seeded default-user inserts from retired MySQL `HR manager/database/schema.sql`; README needs no change. Preserve unrelated dirty hunks. Risk: apply the PostgreSQL migration before the updated HR Manager PHP reads the new column. No dependencies planned.
- S2 plan completed: installed and verified Gitleaks, scanned every ref and full commit history with full redaction, classified findings without exposing values, and recorded only file/commit/line/rule metadata below. No files, secrets, or history were modified by the scan.
- S3 implementation: added an optional system prompt to structured requests; CV, job title/requirements, skills, and derived profile text are explicitly framed as untrusted data, with delimiter-like content escaped. Candidate profile/evaluation prompts now state that these data blocks cannot override instructions, scores, recommendations, or HR decisions. Bumped the affected prompt versions.
- S3 tests: added hostile CV/role-play and fabricated-quote regression coverage, candidate-profile framing coverage, and an offline adapter test that checks the custom system prompt reaches the system message.
- S5 implemented per owner-approved amendments: AES-256-GCM storage envelopes authenticate organization UUID + file UUID + key id; production requires encryption and an active key; no plaintext fallback. Existing-file conversion defaults to dry-run and requires an external verified backup before encrypted temp-copy/checksum verification/atomic replace; reruns resume from the same backup. Retention is disabled by default, org-configurable (12/24 months), dry-run capable, and capped per run. Erasure is admin-only, org-scoped, idempotent, skips legal holds, and audits only IDs/counts. See `docs/storage-encryption-retention.md`.
- S4 verification: `tests/test_auth.py tests/test_alembic.py` → 41 passed; focused Ruff check passed; Ruff formatting check passed for the new model/service/migration and tests. `alembic heads` → single head `029_hr_sso_single_use`. PHP syntax check in `hr_ai_assistant_hr_php` passed. No live database migration or external API call.
- S4 offline migration SQL generation is limited by existing revision `019_candidate_interview_portal_security.py`, whose `upgrade()` iterates the result of a `SELECT` during offline generation and raises `TypeError: 'NoneType' object is not iterable`; this predates S4 and was left unchanged. A pre-existing formatting difference in `auth.py`'s invalid-organization message remains untouched; Ruff check passes and all other touched Python files pass format check.
- S4 files: modified backend auth/model/tests and HR Manager launcher; added assertion-use model/service and migration 029. No dependencies. Commit `17da746`; launcher entry query preserved.
- Existing working tree has many uncommitted edits and untracked files predating this task. They are intentionally untouched; baseline results apply to that working tree.
- The requested path `HR create jop/AGENT_TASKS.md` is absent; the full task plan was read from `HR create jop/docs/AGENT_TASKS.md`. No files were moved.
- T0.0 acceptance pointer in `HR create jop/AGENTS.md` is pending owner action; this agent will not edit that file.

## A4 PLAN [AUTO]
1. Extend `tools/eval_quality.py` to benchmark the configured AI provider through the existing in-memory `CandidateEvaluationWorkflow`; keep the deterministic report mode available.
2. Inspect and reuse the synthetic fixture approach in `tools/eval_ollama_quality.py`; add pure Arabic and mixed-language synthetic CV/JD cases with expected evidence and quote fragments.
3. Meter provider structured calls and per-CV elapsed time without recording prompts, CV text, API keys, or other PII.
4. Report valid structured-JSON rate, evidence precision/recall against the fixture labels, verified grounded-quote rate, average latency, and calls per CV in a compact table.
5. Add offline unit tests for metric calculations and formatting/failure accounting; never call a live or paid provider in tests.
6. Run the benchmark once using only a local deterministic/fake path where feasible, focused tests, Ruff, and `git diff --check`; document that live-provider runs are opt-in and operator initiated.
7. Commit only A4 code, fixtures/tests, and this progress update.

## A3 PLAN [AUTO]
1. Reuse the existing versioned `CandidateProfile` and `CandidateEvaluation` artifacts; avoid a new cache table that duplicates resume-derived personal data.
2. Normalize resume text for cache identity and include prompt version, effective provider/model, and the approved job-profile version for evaluation.
3. Store only cache identity metadata in each artifact's existing provenance; never persist resume text in cache metadata.
4. On same-organization re-screen, reuse a matching current AI profile and completed current evaluation, including their existing evidence and trace IDs, so no provider is called.
5. Treat human-corrected profiles as authoritative; do not replace them from an AI cache. Prompt, model, resume content, or job-profile version changes must miss.
6. Add offline database-backed tests that count provider calls, assert repeat screening hits, and assert job-profile-version changes miss; retain existing organization-scope checks.
7. Run focused tests, Ruff, and diff checks; update task status and commit only A3 code/tests plus this progress entry.

### A3 checkpoint
- Implemented cache identities in existing artifact provenance and same-org current-artifact lookups; no schema change or CV text duplication.
- First focused test run: 61 passed, 7 skipped, 1 failed. The remaining assertion expected an additional evaluation version on identical input; root cause is now understood as an outdated expectation under A3 reuse.
- Second focused test run after updating that expectation: 61 passed, 7 skipped, 1 failed. Root cause: the new job-profile version-miss test referenced `user` while its fixture unpacked the value as `_user`; fix the fixture binding and rerun.
- Focused Ruff check excluding pre-existing E501/B904 diagnostics passed. Strict Ruff still finds 9 diagnostics on untouched lines in the two existing workflow/test files; the new helper passes strict check and format check. `py_compile` and `git diff --check` passed.
- The first repeat-evaluation test expectation and a fixture binding were corrected; final focused run: 62 passed, 7 skipped. No live provider calls.

## A6 PLAN [GATE] — approved with conditions on 2026-11-22
1. Add `AI_MODE` with the existing AI path as the default and an explicit `rules` option; rules mode must bypass all AI provider calls.
2. Reuse and harden existing deterministic matching/quote recovery helpers for English, Arabic, and mixed-language requirement text; do not change official scoring semantics.
3. Route rules evidence through the existing `EvidenceVerificationService`; unverified quotes stay non-positive and HR decisions remain human-controlled.
4. Persist `rules_v1` provenance and a clear rules-only label in the existing evaluation response and review UI so HR can distinguish it from LLM output.
5. Keep changes within backend config/workflow/service/schema, focused backend tests, the review page/tests, and this progress file; no new dependency or database migration planned.
6. Add golden cases for exact/alias matches, partial and missing evidence, Arabic/mixed-language input, and fabricated quote rejection; assert providers are never called in rules mode.
7. Run focused backend/frontend checks and review scoring, evidence verification, and normal AI mode for regressions; commit only A6 files after approval.
8. Owner conditions: use a distinct cache identity containing `ai_mode=rules` and engine `rules_v1`; `matched` requires a quote verified against CV text; default remains the AI path; show an explicit rules-only review notice.

### A6 checkpoint
- Reusing existing deterministic evidence and explanation helpers; they normalize Arabic/English and already route quotes through `EvidenceVerificationService`.
- Added `AI_MODE=llm|rules` with `llm` default. Rules mode bypasses provider generation, uses deterministic matching, re-verifies quotes against the extracted CV, and persists `ai_mode=rules` / `generation_engine=rules_v1`.
- Cache identity includes `ai_mode` and generation engine; rules identity is explicitly `rules`/`rules_v1`, preventing cross-reuse with provider-derived results. Scoring remains the existing deterministic scorer and HR decisions remain human-controlled.
- Review bundle exposes active mode; the review UI labels rules output and explains the mode. Added offline evidence/cache persistence tests and `docs/rules-only-evidence.md`. No migration or dependency.
- Validation: backend workflow + review API selection: 51 passed, 3 skipped, 99 deselected. Frontend review tests: 13 passed. Vite build passed with existing large-chunk warning; targeted Oxlint reports one pre-existing unused `EVALUATION_STATUS_TONE` warning. Ruff check passes with pre-existing E501/B904 ignored; existing format-check drift remains in the two large workflow/test files. `git diff --check` passed. No live provider/API calls.
- Commit: `2290230`.
## TASK STATUS
- S1: done (`b7903e7`).
- S2: done (`e796dba`); no confirmed real secrets found, so no key rotation is pending.
- S3: done (`98a72ce`).
- S4: done (`17da746`; follow-up metering fix `e99d445`).
- S5: done (`1725d09`).
- A3: done (`a6881eb`); cache metadata lives in existing versioned artifacts, with no migration or dependency. Repeat extraction/evaluation reuses current artifacts and traces; resume content, profile version, prompt/schema, or effective provider/model changes miss. Focused tests: 62 passed, 7 skipped. No live AI calls.
- A6: done (`2290230`).
- B1: done (worker lock and cleanup logging fixes; commit `3c4d56e`).
- A1: implemented, live verification pending; distinct self-hosted provider adapters with mocked tests, isolated quotas/usage ledger, and configurable Ollama context. No real model or endpoint was configured.
- S6: pending [GATE] design approval.
- S7: pending [GATE] design approval.

## A2 PLAN [AUTO]
1. Inspect the existing provider config, startup lifecycle, admin AI status endpoint/UI, Docker Compose defaults, and related tests.
2. Add a startup guard that rejects Fake AI in production unless `ALLOW_FAKE_AI=true`; do not change provider selection or silently substitute providers.
3. Log only the effective provider and model at startup, never credentials or endpoint secrets.
4. Expose the effective provider/model through the existing admin status surface, preserving current authorization and API shape where possible.
5. Show a clear demo-AI banner in the UI only when Fake is the effective provider.
6. Add focused backend startup-guard tests and frontend banner tests; run focused checks, lint, and build as required.
7. Review the diff for secret leakage, unintended AI-policy changes, and compatibility before committing A2 alone.

## B1 PLAN [AUTO]
1. Inspect worker, outbox, screening batch services, and relevant tests to map claim locks, retry/backoff, attempt limits, recovery, concurrency, crashes, and failure visibility.
2. Record verified behavior with file-level references; distinguish confirmed defects from design choices.
3. Run focused worker tests first; make only a minimal fix for verified lost or silent failures and add a regression test.
4. Run the focused checks, document limitations, update task status, and commit only B1 changes.

### B1 checkpoint
- Screening batch work uses PostgreSQL `FOR UPDATE SKIP LOCKED` when claiming; claims commit a token and 5-minute lease before processing. Automatic retries are capped at 3 with 30s exponential backoff; expired leases are immediately requeued until attempts are exhausted, then marked failed. Batch polling is every 2s. Public GitHub evidence work uses SKIP LOCKED, a 5-minute lease, 3 attempts, and records terminal failures; rate limits expose retry-after and manual retry is organization-scoped and consent-aware.
- Verified race: after claim commit, both worker paths previously processed without holding the row lock, so stale-lease recovery could reclaim work that was still actively processing after the 5-minute lease. Processing now locks and refreshes the claimed row for the duration of its DB transaction; stale recovery already uses SKIP LOCKED and skips that active lock. Added PostgreSQL-dialect SQL assertions for both paths.
- Verified swallowed failure: cleanup of a newly created resume file suppressed deletion exceptions. It now emits a safe warning with item ID and exception class only; regression test verifies the path is not logged.
- `services/outbox_worker.py` is absent and no outbox worker implementation exists in the backend; audited the actual screening and GitHub analysis queues instead. Unexpected loop exceptions are logged by type and polling continues; item-level failures remain persisted or recover through their lease.
- Focused backend checks: 26 passed, 1 deselected; Ruff check passed; format check passed (4 files); `git diff --check` passed. No dependencies or schema changes.
## A1 PLAN [GATE] — approved with native Ollama conditions on 2026-11-22
1. Keep `ollama` as Ollama Cloud; add `local` for generic OpenAI-compatible self-hosted servers and separate `ollama_local` for native Ollama `/api/chat`.
2. Verify official request/response fields before implementation: `options.num_ctx`, JSON-schema `format`, `prompt_eval_count`, `eval_count`, `done`, and `done_reason`.
3. Add configurable local endpoint/model/API-key settings and Ollama `num_ctx` (default 16384); enforce typed failures for context-boundary or incomplete output and meter every call.
4. Use a distinct self-hosted quota/usage-ledger path without changing external-provider cost authorization; add mocked HTTP tests only for success, JSON schema, truncation, connection error, timeout, and bad JSON.
5. Update provider status labels and configuration docs. Record that real-hardware latency/quantization remain unmeasured until a rented-GPU test.
6. Propose only (do not apply) the OpenRouter paid benchmark control: explicit model allow-list, atomic hard monthly cap, and warning at 80%; use synthetic CVs only and wait for separate approval.
7. Run focused tests, Ruff, and diff checks, update this log, and commit A1 alone.

### A1 completion
- Added separate `local` OpenAI-compatible and `ollama_local` native adapters; retained `ollama` for Ollama Cloud. Models/endpoints remain operator-configured with no guessed model ID.
- Native Ollama sends `/api/chat` with `stream:false`, JSON Schema in `format`, and `options.num_ctx` (default 16384). Prompt-token boundary, incomplete generation, invalid JSON, network failures, and timeouts return typed errors; failures and successes are written to the usage ledger.
- Added separate configurable self-hosted quotas (60 RPM / 1000 daily global; 30 RPM / 300 daily per user by default). External provider quotas and paid authorization behavior are unchanged.
- Admin settings distinguish both self-hosted paths; Verify works for local without requiring a cloud key. Added setup, memory-sizing, verification-state, and paid-benchmark proposal docs. No dependency, schema, prompt, or scoring changes.
- Mocked backend provider/policy/settings checks: 80 passed, 1 skipped. Frontend AI-settings tests: 5 passed. Ruff check and format check passed on all touched Python files; targeted Oxlint and `git diff --check` passed. No live endpoint, model download, paid call, or real CV was used.
- Limit: current official Ollama API docs do not document a tokenizer preflight endpoint; HERA rejects model-reported `prompt_eval_count >= num_ctx` before accepting any result, and rejects any incomplete response. Live endpoint/model verification is pending.
- Performance and quantization effects on real hardware remain unmeasured until a rented-GPU check. OpenRouter paid benchmarking remains disabled pending exact model ID and approval of the proposed allow-list + atomic monthly cap + 80% warning.

## A5 PLAN [GATE] — CPU-only advisory pre-ranking
1. Inspect the screening queue, candidate-profile artifacts, evaluation-state transitions, organization settings, and review UI before coding; preserve the existing LLM evaluator and official scoring path.
2. Add a CPU embedding pre-ranker over job requirements and bounded CV chunks. Rank every application with normalized cosine similarity, then send only the configurable top N to the existing LLM evidence evaluation. Never infer HR decisions or official scores from the advisory rank.
3. Store/show the advisory rank separately from `AI match score`; label it advisory in the UI. For applications below N, record an explicit `not evaluated by LLM: outside top N` state so it cannot be confused with a zero score or failure. HR can still inspect every candidate.
4. Make pre-ranking opt-in and top N organization-configurable; if the selected local embedding model is unavailable, fail visibly before LLM calls rather than silently bypassing the limit. Scope every query and cache key to organization and content version.
5. Add deterministic/synthetic-only tests for Arabic, English, mixed-language matching, ties, top-N boundaries, org isolation, model failure, and proof that advisory output never changes official scoring or HR decisions. Benchmark CPU latency and ranking quality only with synthetic CVs.
6. Candidate model options verified from official Hugging Face/Sentence Transformers pages:
   - `intfloat/multilingual-e5-small`: 0.1B parameters; safetensors weights 471 MB; MIT; supports Arabic (94-language card, Arabic Mr. TyDi results); max input 512 tokens, uses `query:` / `passage:` prefixes. [Model card](https://huggingface.co/intfloat/multilingual-e5-small), [weight file](https://huggingface.co/intfloat/multilingual-e5-small/blob/main/model.safetensors).
   - `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`: 0.1B parameters; safetensors weights 471 MB; Apache-2.0; 50+ languages including Arabic; 384 dimensions and 128-token max sequence length. [Model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), [official language list](https://github.com/huggingface/sentence-transformers/blob/main/docs/sentence_transformer/pretrained_models.md), [weight file](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/blob/main/model.safetensors).
7. Do not add dependencies, download weights, migrate data, or change screening behavior until this plan is approved. Choose the model after synthetic Arabic/English ranking evaluation; no performance claim until CPU measurements exist.

## DONE
- T0.4 | Verified current filters UI was introduced intentionally in `3867aad`; updated only three ApplicationsList tests and the MatchingResults comparison test using accessible roles/names, preserving status/search/filter/compare assertions and keyboard operation. Full frontend suite: 53 files, 339 passed. Ruff: clean; format: 298 files formatted. Commits: format `05b3997`, safe Ruff fixes `4c6ff26`, remaining Ruff `cc67a15`; T0.4 tests/progress commit `807a1a5`.
- T0.0 | Created this progress log; no dependencies.
- T0.1 | Baseline complete; no files changed and no dependencies added.
- T0.2 | Corrected architecture provider list, PostgreSQL screening queue/worker description, and canonical frontend path. Text-only; no dependencies.
- T0.3 | Removed unused development identity page and evaluations redirect component; preserved legacy URLs as redirects and updated dashboard/review navigation. No dependencies.
- S1 | Restricted default seed credentials to development; added production seed guard, password rotation migration/flow, and removed legacy MySQL default account inserts. No dependencies.
- S2 | Gitleaks 8.30.1 scanned 24 refs and 68 commits with `--all --full-history`; 8 generic-key matches were reviewed as test fixtures or a source false positive. No confirmed real secret; no remediation or history changes.
- S3 | Added structured system instructions and untrusted data blocks for CV/job context; escaped spoofed block markers; verified deterministic scoring still rejects unsupported quotes. Focused backend tests: 92 passed, 7 skipped; commit `98a72ce`; no external AI calls or dependencies.
- S4 | Added 45-second assertion lifetime enforcement, 5-second bounded clock skew, random JTI single-use storage (hash only, expiry cleanup), retained issuer/audience and configured-org binding, and documented role mapping; PHP lint + 41 focused tests passed. Commit `17da746`.
- S5 | Added AES-GCM file encryption, verified resumable storage migration, candidate anonymization/deletion, legal holds, retention settings/job, and documentation. Full backend suite: 1105 passed, 1 skipped, 12 deselected; focused S5/storage/Alembic suite: 38 passed. No live migration or retention deletion executed.
- S8 | Added `.github/workflows/security-ci.yml` at the Git repository root. It redacts Gitleaks output and scans only incoming commits (avoids known historical report-only matches); runs Python dependency audit, Ruff, PostgreSQL-backed pytest, production npm audit at high/critical, Oxlint, Vitest, and Vite build. No application files or dependencies changed. Commit: `df7c6e5` (workflow only).
- A2 | Production rejects `AI_PROVIDER=fake` unless `ALLOW_FAKE_AI=true`; startup logs provider/model/demo only; admin settings expose `is_demo`, with a visible simulated-response notice for Fake. Added config/API/UI regression tests and documented the override in both env examples. No dependencies. Backend focused tests: 14 passed, 1 skipped; frontend settings tests: 4 passed; Ruff check+format passed; targeted Oxlint passed; Vite build passed (existing chunk-size warning). `npm run lint` could not resolve its binary because the Windows workspace path contains `&`; direct Oxlint on both changed UI files passed.
- A4 | Added configured-provider synthetic benchmarking with JSON-rate, evidence precision/recall, grounded quote rate, latency and provider-call metrics; shared fixtures now include English, Arabic, mixed-language, missing-evidence, and injection cases. Reused the in-memory candidate-evaluation workflow; reports never print CVs, prompts, keys, or provider messages. Added offline metric, failure, report, and Fake-mode guard tests. No dependencies. Focused tests: 9 passed; Ruff check excluding pre-existing E501 warnings passed; tests format check and `py_compile` passed. Default deterministic run: 9 cases, deterministic=True, stuffing delta=0. No live provider request was made. Provider command: `python tools/eval_quality.py --provider-benchmark` (configured provider in `backend/.env`; sends only synthetic fixtures). Strict Ruff still reports 12 pre-existing E501 lines in `tools/eval_quality.py`, and the legacy file-wide format check proposes unrelated formatting changes.
- A3 | Reused current versioned candidate profiles/evaluations based on hashed normalized resume content, job-profile/candidate-profile versions, prompt/schema versions, provider/model identity, and evaluation engine version. Stored only hashes and prior trace IDs in artifact provenance; no CV text, new table, migration, or dependency. Added call-count tests for cache hits and profile-version/content misses. Focused tests: 62 passed, 7 skipped; `py_compile`, added helper Ruff check/format, filtered Ruff, and `git diff --check` passed. Strict Ruff reports 9 existing E501/B904 diagnostics on untouched lines in the large workflow/test files. No external AI calls.

### S8 local run

From repository root, run Gitleaks on the current commit:
`docker run --rm -v "${PWD}:/path" ghcr.io/gitleaks/gitleaks:v8.30.1 git --redact --no-banner --log-opts="-1" /path`

Backend, from `HR create jop/backend` (provide a safe local PostgreSQL test DB in `TEST_DATABASE_URL`):
`python -m pip install -e ".[dev]" pip-audit`; `pip-audit`; `ruff check .`; `pytest -m "not soal" -q --tb=short`.

Frontend, from `HR create jop/frontend/frontend_last`:
`npm ci`; `npm audit --omit=dev --audit-level=high`; `npm run lint`; `npm test -- --reporter=dot`; `npm run build`.

- S8 verification: PyYAML parsed the workflow and confirmed all three jobs; `git diff --check` passed. The first parser attempt used a YAML package absent from the local frontend install; switched to the already-installed backend PyYAML successfully. GitHub-hosted workflow execution was not available in this local session; full lint/test/build/audit jobs were not rerun because their pre-existing baseline outcomes are already recorded above and this task only adds workflow configuration.

## BLOCKED
- NEEDS_HUMAN | W1 | Select messaging provider; provide credentials, approved templates, and opt-in/legal wording | Integration and candidate consent cannot be invented | Once supplied, prepare the gated plan | Continue other unblocked tasks.
- NEEDS_HUMAN | A1 benchmark policy | Supply exact OpenRouter model ID and approve a proposed allow-list/monthly-cap policy before any paid benchmark | No model ID or paid-spend authorization has been provided | Submit the minimal policy proposal; implement only after explicit approval | Core self-hosted providers and mocked tests proceed without a model ID or live endpoint.
- NEEDS_HUMAN | A5 | Approve proposed default top N=20 and explicit below-N state (“not evaluated by LLM; advisory rank only”) | These determine evaluation scope and candidate-facing state | Implement the bounded advisory flow only after approval | Plan and verified model candidates are documented; no code or weights changed.

## DECISIONS
- Preserve all pre-existing working-tree changes and exclude them from T0.0 commit.
- Use `HR create jop/docs/AGENT_TASKS.md` as the actual task plan because the instructed root path does not exist.
- S5 approved policy: `cryptography` runtime dependency; missing active key fails startup; production encryption mandatory; AES-GCM AAD binds org + file IDs; verified external backup precedes atomic replacement; plaintext verification stays in memory; retention defaults remain inactive until `RETENTION_ENABLED=true`; deletion anonymizes candidates and removes files/text/evaluations/evidence while retaining HR decisions, interviews, and audit IDs.

## PROPOSALS

## FACTS
- Repo root: `C:\Users\LOQ\Documents\HRsmart&HR-HERA\HR-Project`.
- Canonical backend: `HR create jop/backend`; canonical frontend: `HR create jop/frontend/frontend_last`.
- S4 final assertion claim set: required `iss`, `aud`, `sub`, `name`, `role`, `iat`, `exp`, and `jti`. Issuer comes from `HR_SSO_ISSUER` (default `hr-manager`), audience is the fixed `hera-recruitment`, `sub` is the HR employee code, `name` is the HR display name, and only `role=hr` is accepted; the backend maps it to `recruiter` plus `hr_operations`. PHP signs HS256 with the shared secret, with `iat` and `exp=iat+45s`, random 128-bit `jti`; backend enforces max lifetime 45s and 5s clock skew, issuer/audience and signature, and consumes a SHA-256 hash of `jti` through assertion expiry plus skew. PyJWT HS256 verification uses `hmac.compare_digest`. Organization is fixed by backend `HR_SSO_ORGANIZATION_ID`, validated active; the PHP assertion cannot select a tenant. Failures return generic invalid/expired assertion errors or safe setup messages.
- S5 files added: `backend/app/core/crypto.py`, `backend/app/services/candidate_privacy_service.py`, `backend/tools/migrate_storage_encryption.py`, `backend/app/cli/retention.py`, migration `030_privacy_retention.py`, tests `test_s5_storage_security.py` and `test_s5_candidate_privacy.py`, and `docs/storage-encryption-retention.md`. Updated dependency metadata, storage callers, candidate/organization models, admin candidate routes, `.env.example`, and Alembic head assertion.
- S5 validation: focused tests 38 passed; final backend `pytest -m "not soal" -q --tb=short`: 1105 passed, 1 skipped, 12 deselected. S5 implementation Ruff checks passed; format check passed for S5-owned files. Two touched legacy worker tests have unrelated existing `I001`/`E501` drift; only fake storage read signatures were updated for ownership context. Alembic reports one head `030_privacy_retention`; migration CLI exposes `--dry-run`/`--apply`. No real storage migration, database migration, retention deletion, or external AI call was run.
- S5 limits: extracted text/evidence in PostgreSQL remain plaintext by approved scope; backups retain deleted data until expiry; historical audit/interview text is preserved. Retention remains disabled pending explicit deployment activation. Commit `1725d09`.
- Required baseline commands have been run; see the compact results below.
- Baseline results on the existing dirty tree: `ruff check .` failed with 194 issues; `ruff format --check .` found 51 files unformatted; backend pytest `-m "not soal" -q --tb=short`: 1079 passed, 1 skipped, 12 deselected; frontend oxlint: 0 errors, 7 warnings; frontend Vitest: 332 passed, 4 failed across 53 files; frontend Vite build succeeded (bundle-size warning: JS chunk 1,063.62 kB).
- Vitest needed direct `node node_modules/vitest/vitest.mjs run --reporter=dot` because Windows `cmd` splits the workspace path at `&`; the equivalent `npm test` also failed under a temporary drive alias because the Vite setup-file path was then resolved incorrectly. `npm run lint` and `npm run build` succeeded via that temporary alias.
- JobDetails failures reported in the task plan are not reproducible: current worktree `JobDetails.test.jsx` passes 18/18; clean base commit `b3c9392` passes its original 17/17 tests. Thus the four-failure note is stale for the available revisions; no JobDetails test or implementation was changed for T0.1.
- The four full-suite failures are elsewhere: three `ApplicationsList` tests cannot find the expected helper text / Advanced button / searchbox accessible name; one `MatchingResults` test finds duplicate “Ada Lovelace” text in its dialog query. No fixes were made during baseline.
- Files inspected: `HR create jop/docs/AGENT_TASKS.md` (tasks and operating rules); `HR create jop/AGENTS.md` (environment and commands); `HR create jop/docs/development-rules.md` (approval and error protocol).
- T0.2 source verification: provider settings/factory in `backend/app/core/config.py` and `backend/app/ai/providers/factory.py`; default `openrouter`, choices `fake`/`soal`/`ollama`/`openrouter`. Worker startup in `backend/app/main.py` and `backend/app/core/config.py`; PostgreSQL queue models in `backend/app/models/screening_batch.py` and `screening_batch_item.py`; claim behavior in `backend/app/worker.py`. Canonical frontend path is confirmed by `docker-compose.yml` build context `./frontend/frontend_last`.
- T0.2 validation: repository `rg` checks matched all edited architecture claims; `git diff --check -- 'HR create jop/ARCHITECTURE.md'` passed. No tests run (documentation-only task).
- T0.3 read-only audit: references were searched across canonical FE source/tests. Key consumers: `App.jsx` imports/routes; `Dashboard.jsx` has two `/evaluations` links; `Dashboard.test.jsx` asserts one; `EvaluationsList.test.jsx` asserts the legacy redirect; `ApplicationReview.jsx` navigates to `/matching`; `ApplicationReview.test.jsx` provides that route. No tests run; no frontend source files changed.
- T0.3 implementation files: `FE/src/App.jsx`; new `FE/src/components/common/LegacyRedirect.jsx` + test; `FE/src/pages/dashboard/Dashboard.jsx` + test; `FE/src/pages/review/ApplicationReview.jsx` + test; removed `FE/src/pages/evaluations/EvaluationsList.jsx` + its superseded redirect test, and `FE/src/pages/identity/DevelopmentIdentity.jsx`. Preserved `/identity`, `/evaluations`, and `/matching` URL compatibility; matching redirects preserve query/hash.
- T0.3 validation: focused tests: 4 files, 24 passed. Full frontend suite: 51 files passed, 2 files failed; 333 passed and 4 failed (the same pre-existing ApplicationsList assertions and MatchingResults duplicate-name assertion recorded at T0.1). Oxlint: 0 errors, 7 warnings. Vite build succeeded with existing large-chunk warning. No dependencies added. No unrelated failing tests were edited.
- S1 audit facts: `tools/seed_hr_manager.py` currently uses a built-in seed fallback, hashes it for fresh accounts, and prints it; `tools/setup_local.ps1` calls the seed and also prints credentials. README contains no seed password literal. `HR manager/database/schema.sql` is legacy MySQL DDL with default-user inserts; active HR Manager uses PostgreSQL `hr_ops.users` created by Alembic migration `020_hr_ops_schema`. `HR manager/login.php` verifies passwords and creates a session; `includes/auth.php::requireLogin()` refreshes the current user's identity/role on each request but has no forced-change gate. No self-service password change route exists. `api/employees.php` can set/reset passwords. Existing password policy helper: `backend/app/cli/bootstrap.py::read_and_validate_password()` (8-character minimum plus common-password rejection). S1 audit did not print credential values in the report. No code changes or dependencies added for S1 yet.
- S1 implementation: `tools/seed_hr_manager.py` keeps the current test password only for development; outside development it fails without an explicit password and rejects weak/default values, never printing credentials. `tools/setup_local.ps1` passes APP_ENV/seed password from the process or backend `.env` and suppresses credential output. New `028_hr_ops_pw_rotate` migration adds the flag. `HR manager/change_password.php` allows only authenticated forced-change sessions to proceed; `includes/auth.php` gates protected pages/APIs, and login redirects to the change form. New/admin-reset passwords are marked for rotation. Legacy MySQL schema no longer inserts default accounts. Passwords for environment-specific seed users remain identical; seed upsert does not replace existing password hashes.
- S1 validation: focused seed policy tests 9 passed; Ruff check passed; Alembic reports `028_hr_ops_pw_rotate` as head; PHP syntax checks passed for all 4 changed PHP files using the app container; PowerShell parser passed; `git diff --check` passed. Ruff format check passes for migration/tests but reports one pre-existing unformatted long statement in `seed_hr_manager.py` (schema existence query); left unchanged to avoid unrelated formatting. No live DB migration or end-to-end login was run. No dependencies added.
- S2 scan: Gitleaks was absent and was installed with WinGet (`Gitleaks.Gitleaks` 8.30.1; package checksum verified). Version and `git` subcommand were verified using the package executable because this PowerShell process did not refresh PATH. A strict full-redaction `gitleaks git` scan used `--log-opts="--all --full-history"` and included all refs; 24 refs and 68 commits were scanned. It reported 8 `generic-api-key` matches (exit code 1 indicates findings). The report was captured and parsed in memory; no report file or secret value was emitted.
- S2 findings (reviewed with values redacted):

| File | Commit | Line | Classification |
|---|---|---:|---|
| `HR create jop/backend/tests/test_seed_hr_manager.py` | `b7903e77d2e1` | 33 | Development-only test seed assertion; not a production credential |
| `HR create jop/backend/tests/test_public_applications.py` | `3867aad8c276` | 196 | Test fixture |
| `HR create jop/backend/tests/test_public_applications.py` | `3867aad8c276` | 410 | Test fixture |
| `HR create jop/backend/tests/test_api.py` | `8d9501348074` | 2484 | Test fixture |
| `HR create jop/backend/app/api/v1/routes/auth.py` | `6c101b208cd0` | 140 | False positive: audit-event argument, not a credential assignment |
| `HR create jop/backend/tests/test_audit_trail.py` | `6c101b208cd0` | 506 | Test fixture |
| `HR create jop/backend/tests/test_prompt6_observability.py` | `6c101b208cd0` | 229 | Placeholder/fake test value |
| `HR create jop/backend/tests/test_api.py` | `6c101b208cd0` | 990 | Test fixture |

- No confirmed real credential was identified among these findings. A separate targeted check of historical key-name references and `.env` examples found documentation/blank/placeholder references only, with no credential assignment verified. These are scanner-pattern-based findings, not a guarantee against every possible secret format. No remediation, file edit, or history rewrite was performed for S2.
- S3 files: `backend/app/ai/markers.py`, `backend/app/ai/providers/base.py`, `backend/app/ai/providers/openai_compatible.py`, `backend/app/ai/workflows/candidate_profile_extraction.py`, `backend/app/ai/workflows/candidate_evaluation.py`, and focused backend tests. No dependencies or migrations added. Prompt versions: candidate profile 2; candidate evaluation 4.
- S3 validation: focused pytest on candidate profile extraction, candidate evaluation, OpenRouter adapter, and evidence engine: 92 passed, 7 skipped. `git diff --check` passed. Ruff checks excluding the baseline `E501`/`B904` findings passed; strict Ruff still reports 9 pre-existing style/error findings in the already-dirty evaluation workflow/test files. Formatter check passes for the cleanly modified files; the evaluation workflow/test files have pre-existing formatting drift, left intact to avoid reformatting owner changes. No live AI call was made.
- S3 environment issue: the first pytest invocation used `..\\.venv` while already in `backend/` and failed to locate Python; confirmed `.venv` exists locally, corrected to `.\\.venv`, and the focused suite passed.
- S3 committed as `98a72ce`; migration dependency revision 027 was committed with the preceding free-first task (`43b7886`).
- A4 checkpoint: first Ruff audit found the new benchmark helpers were inserted before the existing `compute_metrics` function body ended, leaving its remaining statements unreachable/out of scope. Root cause was patch placement at the wrong closing brace; moving the original body back under its function before continuing.
- A4 checkpoint: fixture score test found the new Arabic synthetic case expected 60 while the unchanged weighted scorer computes 62.5 (must-have 3 + important 2, with a third missing must-have weight 3). Update only the fixture expectation to the verified deterministic score and rerun the focused suite.
- A4 checkpoint: the expectation edit matched the first occurrence of `60` and changed the pre-existing sparse case instead of the new Arabic case. Restore the sparse case score to 60 and set 62.5 only on the Arabic case by ID.

- A4 resolved checkpoints: moved benchmark helpers below the existing deterministic metric function after a placement error; corrected the Arabic fixture expectation to the scorer-verified 62.5 and restored the existing sparse-case expectation to 60 after an initially broad replacement.

- T0.4 broader backend run (outside approved frontend-only edits): 1114 passed, 1 skipped, 12 deselected, 3 failed. The rate-limit case is order-dependent because prior public-application requests persist a shared TestClient-IP bucket; two worker cases can claim stale queued rows whose temporary files expired. No backend tests/code changed in this authorized frontend task.


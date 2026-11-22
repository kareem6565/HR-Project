# Agent Progress

## CURRENT
- Task: A3 [AUTO] complete. Next in Section 5: A1 [GATE + NEEDS-HUMAN], blocked until local LLM base URL, exact model, and structured-output support are supplied.
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
## TASK STATUS
- S1: done (`b7903e7`).
- S2: done (`e796dba`); no confirmed real secrets found, so no key rotation is pending.
- S3: done (`98a72ce`).
- S4: done (`17da746`; follow-up metering fix `e99d445`).
- S5: done (`1725d09`).
- A3: done; cache metadata lives in existing versioned artifacts, with no migration or dependency. Repeat extraction/evaluation reuses current artifacts and traces; resume content, profile version, prompt/schema, or effective provider/model changes miss. Focused tests: 62 passed, 7 skipped. No live AI calls.
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

## DONE
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
- NEEDS_HUMAN | A1 | Supply local LLM base URL, exact model name, and structured/JSON output support | Provider behavior must not be guessed | Once supplied, complete the gated local provider implementation | Until then, use a mocked HTTP server only.
- NEEDS_HUMAN | A5 | Approve embedding model and available hardware/resources | Model footprint and dependency depend on this choice | Once supplied, prepare the gated plan | Continue unblocked tasks without model assumptions.
- NEEDS_HUMAN | W1 | Select messaging provider; provide credentials, approved templates, and opt-in/legal wording | Integration and candidate consent cannot be invented | Once supplied, prepare the gated plan | Continue other unblocked tasks.

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

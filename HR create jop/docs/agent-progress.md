# Agent Progress

## CURRENT
- Task: S1 [GATE] plan posted; awaiting owner approval before credential-policy changes.
- Branch: `agent/recruitment-work` (created from the existing `feat/public-candidate-application` tree).
- Baseline plan executed: (1) preserve existing local edits; (2) run backend lint, format, and non-Soal pytest; (3) run frontend lint, tests, and build; (4) isolate the reported JobDetails failures; (5) record summaries. T0.2 is now complete.
- T0.3 plan was approved and completed: audit references; delete unused identity UI and evaluations redirect component; replace legacy URLs with query/hash-preserving redirects; point dashboard actions and review navigation at canonical routes; update focused route tests; run frontend validation; commit only task files.
- S1 plan: (1) inspect `tools/seed_hr_manager.py`, `README.md`, `HR manager/database/schema.sql`, and `HR manager/login.php` for default credentials and actual seed/login behavior; (2) verify whether legacy SQL credentials are still used; (3) propose environment guard, must-change-password flow, and tests without changing authentication design beyond task scope; (4) wait for owner approval before implementation because S1 is [GATE]; (5) do not expose credential values in reports.
- Existing working tree has many uncommitted edits and untracked files predating this task. They are intentionally untouched; baseline results apply to that working tree.
- The requested path `HR create jop/AGENT_TASKS.md` is absent; the full task plan was read from `HR create jop/docs/AGENT_TASKS.md`. No files were moved.
- T0.0 acceptance pointer in `HR create jop/AGENTS.md` is pending owner action; this agent will not edit that file.

## DONE
- T0.0 | Created this progress log; no dependencies.
- T0.1 | Baseline complete; no files changed and no dependencies added.
- T0.2 | Corrected architecture provider list, PostgreSQL screening queue/worker description, and canonical frontend path. Text-only; no dependencies.
- T0.3 | Removed unused development identity page and evaluations redirect component; preserved legacy URLs as redirects and updated dashboard/review navigation. No dependencies.

## BLOCKED
- None.

## DECISIONS
- Preserve all pre-existing working-tree changes and exclude them from T0.0 commit.
- Use `HR create jop/docs/AGENT_TASKS.md` as the actual task plan because the instructed root path does not exist.

## PROPOSALS
- None.

## FACTS
- Repo root: `C:\Users\LOQ\Documents\HRsmart&HR-HERA\HR-Project`.
- Canonical backend: `HR create jop/backend`; canonical frontend: `HR create jop/frontend/frontend_last`.
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

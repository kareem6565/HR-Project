# Agent Progress

## CURRENT
- Task: T0.3 [GATE] plan posted; awaiting owner approval before removing any UI code.
- Branch: `agent/recruitment-work` (created from the existing `feat/public-candidate-application` tree).
- Baseline plan executed: (1) preserve existing local edits; (2) run backend lint, format, and non-Soal pytest; (3) run frontend lint, tests, and build; (4) isolate the reported JobDetails failures; (5) record summaries. T0.2 is now complete.
- T0.3 plan: (1) inspect `FE/src/config/routes.js`, `FE/src/App.jsx`, navigation, imports, and tests for each candidate in T0.3; (2) report whether each page/route/button is genuinely dead and list exact affected files; (3) make no deletions or route changes until owner approval; (4) after approval, remove only approved items and update focused tests; (5) run the task-required frontend checks and commit T0.3 separately.
- Existing working tree has many uncommitted edits and untracked files predating this task. They are intentionally untouched; baseline results apply to that working tree.
- The requested path `HR create jop/AGENT_TASKS.md` is absent; the full task plan was read from `HR create jop/docs/AGENT_TASKS.md`. No files were moved.
- T0.0 acceptance pointer in `HR create jop/AGENTS.md` is pending owner action; this agent will not edit that file.

## DONE
- T0.0 | Created this progress log; no dependencies.
- T0.1 | Baseline complete; no files changed and no dependencies added.
- T0.2 | Corrected architecture provider list, PostgreSQL screening queue/worker description, and canonical frontend path. Text-only; no dependencies.

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

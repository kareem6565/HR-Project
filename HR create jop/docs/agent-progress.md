# Agent Progress

## CURRENT
- Task: T0.1 complete; next unblocked task is T0.2 [AUTO].
- Branch: `agent/recruitment-work` (created from the existing `feat/public-candidate-application` tree).
- Baseline plan executed: (1) preserve existing local edits; (2) run backend lint, format, and non-Soal pytest; (3) run frontend lint, tests, and build; (4) isolate the reported JobDetails failures; (5) record summaries and stop before T0.2.
- Existing working tree has many uncommitted edits and untracked files predating this task. They are intentionally untouched; baseline results apply to that working tree.
- The requested path `HR create jop/AGENT_TASKS.md` is absent; the full task plan was read from `HR create jop/docs/AGENT_TASKS.md`. No files were moved.
- T0.0 acceptance pointer in `HR create jop/AGENTS.md` is pending owner action; this agent will not edit that file.

## DONE
- T0.0 | Created this progress log; no dependencies.
- T0.1 | Baseline complete; no files changed and no dependencies added.

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

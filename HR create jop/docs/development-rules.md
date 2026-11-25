# Development Rules

## Core Process

Follow this process for project work:

```
PLAN -> APPROVAL -> IMPLEMENT -> TEST -> REVIEW -> COMMIT
```

Do not skip the planning stage.

Do not write code before approval when the task requires approval.

## Incremental Development

Work incrementally.

Do not implement the entire application at once.

Work on one small task at a time.

Preserve existing functionality when implementing new features.

## Before Modifying Files

Before modifying code or substantial project files, explain:

- What will change.
- Which files will be created.
- Which files will be modified.
- Why each change is necessary.

Wait for approval before implementing substantial changes.

## Scope Control

Do not modify unrelated files.

Do not introduce dependencies without explaining why they are necessary.

Do not introduce new frameworks without approval.

Do not redesign the architecture without approval.

Prefer simple, maintainable code over unnecessary abstractions.

Do not over-engineer the MVP.

## Codebase Optimization \& Minimal Changes

Before writing new code, inspect the existing codebase and reuse existing implementations whenever possible.

Prefer the smallest change that fully satisfies the task requirements.

Do not duplicate existing functionality or create unnecessary files, classes, services, or abstractions.

Do not add features, enhancements, or behavior that were not explicitly requested.

Avoid unnecessary code expansion. Keep implementations simple, focused, and maintainable.

When modifying existing code, preserve its current behavior unless the task explicitly requires changing it.

For existing codebases, identify opportunities to simplify complex code, remove duplicate code, and eliminate unused code when it is safe to do so.

Do not remove code without verifying that it is not used by other components, integrations, or workflows.

Do not perform broad refactoring, restructuring, or optimization outside the task scope without approval.

When optimization is requested, work incrementally and run appropriate tests after each change.

Do not optimize for fewer lines of code at the expense of readability, maintainability, or correctness.

## Development Environment \& Runtime Verification

Before implementing changes, identify the exact project directory, running frontend/backend processes, ports, and execution environment.

Ensure code changes are applied to the same project instance served by the local development environment.

After implementation:

- Verify that the running application reflects the changes.
- Check whether hot reload is working.
- Verify the correct frontend and backend ports.
- If Docker is used, verify volume mappings and container synchronization.
- Restart or rebuild services only when necessary.
- Do not claim that changes are visible or working without runtime verification.
- Report when manual intervention or a service restart is required.

## Time \& Execution Efficiency

Work efficiently without sacrificing code quality, correctness, or reliability.

1. Avoid reading or scanning unrelated files.
2. Inspect only files relevant to the current task.
3. Avoid unnecessary full-project scans.
4. Do not repeat successful commands without a valid reason.
5. Avoid running the same tests repeatedly unless investigating a failure.
6. Prefer targeted tests when full test suites are not necessary.
7. Avoid unnecessary rebuilds, restarts, and dependency installations.
8. Do not introduce new dependencies unless required.
9. If a command or operation fails repeatedly, stop and analyze the root cause instead of retrying blindly.
10. If execution takes unusually long, identify the bottleneck and report it.
11. Do not skip necessary tests or verification just to finish faster.
12. Keep the implementation and execution process focused on the requested task.

**Priority:** Minimize unnecessary work, not necessary engineering work.

## AI And Agent Rules

Do not create an AI agent when a normal service or function is sufficient.

Before introducing an agent, evaluate whether it genuinely needs reasoning, decision-making, tools, state, or autonomous planning.

Use typed interfaces and structured schemas.

Validate all important LLM outputs.

Business-critical decisions must not depend solely on LLM output.

Keep business logic separate from AI and LLM infrastructure.

Keep external integrations behind clear service or tool interfaces.

Keep HR as the final decision maker.

## Testing Rules

Every completed feature must have appropriate tests.

Never remove or weaken tests just to make them pass.

Do not randomly change prompts, models, architecture, and business logic simultaneously when debugging.

After implementation, report:

- Files changed.
- Files created.
- Dependencies added.
- Implementation summary.
- Tests added.
- Tests executed.
- Test results.
- Known limitations.
- Possible risks.

## Error Protocol

When an error occurs, do not immediately modify code.

First analyze:

1. Exact error.
2. Root cause.
3. Component responsible.
4. Whether it is a code, data, prompt, model, API, database, or infrastructure issue.
5. Proposed fixes.
6. Risks of each fix.

Then wait for approval before implementing the fix when the fix changes code or architecture.

Never hide errors with broad exception handling.

## Observability

Maintain observability, especially for AI workflows.

The system should be able to identify:

- Workflow run.
- Graph node.
- AI component or agent.
- Model/provider.
- Prompt version.
- Input/output schema.
- Latency.
- Token usage when available.
- Validation errors.
- Retries.
- Final status.
- Failure location.

Observability is infrastructure. Do not create an Error Tracking Agent.

## Documentation And Commit

Document important decisions.

After work is implemented and reviewed, commit each milestone when requested or approved.

Do not proceed to the next feature until the current feature has completed the agreed process.

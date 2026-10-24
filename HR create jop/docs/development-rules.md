# Development Rules

## Core Process

Follow this process for project work:

```text
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

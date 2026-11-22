# HERA Free-First AI Cost Policy

**Status:** Implemented in backend source; migration and deployment still required before runtime enforcement.

## Policy

- External inference is permitted only through `https://openrouter.ai/api/v1`.
- `openrouter/free` is the default route. OpenRouter documents it as routing each chat request to a free model that fits it.
- Explicit model IDs are allowed only when they end in `:free`, appear in `AI_FREE_MODEL_ALLOWLIST`, and the current public catalog reports both prompt and completion prices as zero. Catalog eligibility is cached for ten minutes and a catalog outage fails closed.
- Text input and text output are required. Structured requests to explicit models additionally require catalog support for `response_format`. Structured requests sent to `openrouter/free` require parameter-compatible provider routing.
- Soal, Ollama, paid DeepSeek, unknown models, nonzero or missing prices, noncanonical endpoints, and nonzero budgets are blocked before inference.
- There is no paid fallback, no user-facing paid switch, and no runtime approval API. Setting `AI_PAID_MODE_ENABLED=true` or a nonzero `AI_PAID_BUDGET_USD` still blocks requests until a separately reviewed owner-approval mechanism exists.
- Explicit `AI_PROVIDER=fake` remains available for tests/offline development. Missing provider selection defaults to OpenRouter; missing credentials fail closed rather than selecting Fake.

## Limits

Shared PostgreSQL counters use atomic upserts and UTC windows. SQLite is supported for local tests. Defaults are 15 requests per minute and 40 per UTC day globally, plus 5 per minute and 20 per UTC day per authenticated user. Workers without an authenticated user still consume global quota. Each outbound attempt, including provider retry attempts, reserves quota before network access. A request rejected at a limit is returned as HTTP 429; quota exhaustion never changes the model.

OpenRouter currently documents a 20 requests/minute and 50 requests/day cap for `:free` variants, with failed attempts counting toward the daily cap. HERA keeps a reserve below those published limits. See [OpenRouter free models](https://openrouter.ai/collections/free-models).

## Cost guard and monitoring

The shared OpenAI-compatible client is guarded by default, including direct provider construction, and checks the policy immediately before every inference HTTP request. OpenAI SDK automatic retries are disabled so every outbound attempt is metered. A separate HTTP GET of the public catalog is used only to verify explicitly allowlisted models; it does not send an inference request or an API key. OpenRouter documents the free router and free pricing in its [free models guide](https://openrouter.ai/collections/free-models); structured routing uses the documented [`require_parameters` provider preference](https://openrouter.ai/docs/guides/routing/provider-selection).

`ai_usage_events` records actor/organization references when available, feature, provider/model, timestamps, request IDs, token counts when returned, reported cost when returned, status, HTTP status, and a bounded error category. It never stores prompts, responses, authorization headers, or API keys. `ai_usage_counters` stores the shared global and per-user windows. `ai_policy_controls.cost_alert` is a persistent global circuit breaker: any reported nonzero cost pauses later inference until an operator investigates and clears it through controlled database operations.

OpenRouter free status and model rates can change. The guard rechecks the public catalog for each explicitly approved `:free` model on cache expiry. The `openrouter/free` router is allowed by its documented contract and is further constrained for structured output; actual model routing and quality are intentionally not inferred from a zero-cost catalog entry.

## Privacy and limitations

Usage rows contain internal user and organization UUID references but no HR payload. The provider adapter does not persist or log prompt/response bodies. Existing prompts and workflows remain unchanged; data minimization within every workflow has not been fully reviewed, and OpenRouter/provider retention and free-tier data handling are not identical across upstream providers. Do not submit real CVs for smoke verification until privacy terms and owner policy have been reviewed. Automated tests use synthetic strings and mocked responses.

## Paid activation

Paid inference remains disabled, budget is zero, and there is no code path for an application user to enable it. A future activation would need a separate owner-only approval record binding exact provider/model, a hard USD cap, and expiration, plus audit and enforcement tests. That activation mechanism is not implemented here.

## Deployment notes

Migration `027_ai_free_first` must be applied before enabling live AI calls; the guard fails closed if usage tables are unavailable. For the default free route, configure `AI_PROVIDER=openrouter`, `OPENROUTER_MODEL=openrouter/free`, and the operator-managed `OPENROUTER_API_KEY` in the backend environment. Current local runtime settings are not changed by this source implementation. No paid or free inference request was sent as part of implementation.

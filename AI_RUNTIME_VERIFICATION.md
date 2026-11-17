# HR-HERA Production AI Runtime Verification

**Verification date:** 2026-11-14  
**Mode:** Runtime verification; no model inference or database reset.  
**Result:** Application started successfully using the existing Compose project and database volume. OpenRouter authentication and public model metadata were verified from the rebuilt Backend container.

## Startup and data safety

The README documents full-stack startup with `docker compose up --build -d`; the Compose Backend service is named `backend`. Compose defines five services:

| Service | Dependency / status |
|---|---|
| `postgres` | No Compose dependency; healthy. |
| `backend` | Waits for healthy `postgres`; healthy. |
| `frontend` | Waits for healthy `backend`; running (no healthcheck is configured). |
| `hr_php` | Waits for healthy `postgres`; healthy. |
| `hr_web` | Waits for healthy `hr_php`; healthy. |

Backend startup runs `alembic upgrade head` before Uvicorn. The database was at `026_github_evidence` before startup and remains at `026_github_evidence` after startup; this is the current Alembic head, so there was no pending migration to apply. The migration scan found an earlier security migration which hashes invitation tokens and then drops the raw token column, but it was already applied and did not run during this startup.

A first Postgres start attempt with the directory’s default Compose project name hit a fixed-container-name conflict with an existing stopped container. No container or volume was removed. Inspection showed the existing stack label was `hr-ai-assistant`; restarting the existing Postgres under that project name with `--no-recreate` attached the existing `hr-ai-assistant_postgres_data` volume. Full-stack startup then succeeded with `docker compose -p hr-ai-assistant up --build -d`. The initial build left the stopped app containers on older image IDs, so only the `backend`, `frontend`, and `hr_php` application containers were force-recreated from the images just built (`--no-deps`); Postgres and its volume were left untouched.

No `.env`, Docker Compose, source, or database contents were edited or reset. The Backend startup migration command ran, but the database was already at the current head both before and after.

## Runtime verification

| Check | Result | Evidence |
|---|---|---|
| Docker Engine | **Available** | Docker Engine `29.8.1`. |
| Compose project | **Running** | Existing project name `hr-ai-assistant`; all five services are up. |
| Backend service | **Healthy** | Docker health status `healthy`; `GET http://127.0.0.1:8000/api/v1/health` returned HTTP 200. |
| Frontend | **Running** | `GET http://127.0.0.1:8080` returned HTTP 200. |
| HR Manager web | **Healthy** | Docker health status `healthy`; login URL returned HTTP 200. |
| Effective `AI_PROVIDER` | **`openrouter`** | Read from the running Backend container environment. |
| Effective model | **`deepseek/deepseek-v4.1-flash-1017`** | Read from the running Backend container environment; matches merged Compose config and expected model. |
| OpenRouter key variable | **Present; value not displayed** | Presence checked inside Backend container. |
| Fake Provider | **Inactive** | Effective provider is OpenRouter and the key variable is present. Provider factory selects OpenRouter for this configuration. The runtime Soal-key override is in-memory and the runtime key modification endpoint is disabled; this is a fresh Backend process. |
| Built app images | **In use** | Backend, Frontend, and PHP container image IDs match the images built from the current Compose contexts. |
| Database schema revision | **`026_github_evidence`** | Queried before and after app startup; same current head. |

### Environment source reconciliation

- Compose project `.env` supplies `AI_PROVIDER=openrouter`; the Backend service’s explicit Compose `environment` mapping passes this value into the container and overrides `AI_PROVIDER=ollama` from `backend/.env`.
- `OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash-1017` is inherited through the Backend service `env_file` (`backend/.env`); the Compose `environment` mapping does not override it.
- The running container values were read directly after container recreation and match the merged Compose configuration. No secrets were printed.

## OpenRouter authentication and quota

An authenticated `GET https://openrouter.ai/api/v1/key` was sent from the running Backend container using its existing `OPENROUTER_API_KEY`. The response was filtered before output; key text, labels, hashes, user/workspace identifiers, and the raw response body were not displayed.

| Field | Returned value |
|---|---:|
| HTTP status | `200` |
| Authentication | **Succeeded** |
| `is_free_tier` | `true` |
| Usage | `$0.147137533` |
| Daily usage | `$0` |
| Weekly usage | `$0.147137533` |
| Monthly usage | `$0.147137533` |
| Key limit | `$2.00` |
| Remaining limit | `$1.852862467` |
| Reset period | Not returned |

The response also contained `rate_limit.requests=-1` and `interval=10s`; OpenRouter documents this `rate_limit` field as deprecated, so it is not treated as a meaningful quota. The account is marked free tier and has positive key-limit remaining. This check does not send an inference request or prove a paid model completion will be accepted; the selected DeepSeek model is priced, and no generation was attempted.

## Model catalog, modalities, and routing

From inside the rebuilt Backend container, an unauthenticated public `GET https://openrouter.ai/api/v1/models` returned HTTP 200. The exact configured ID was present with:

- Input modalities: text and image.
- Output modality: text.
- Context length: 1,048,576 tokens.
- `response_format` supported: yes.
- Public catalog rates: $0.038 per million input tokens, $0.50 per million output tokens, and $0.01 per million cached input tokens.

The model ID configured in HERA matches the model returned by the catalog. No completion was sent, so the actual upstream provider selected for a generation was not observed. OpenRouter routes a model across eligible providers according to routing policy and provider conditions; actual serving endpoint and billed rate can vary. Pin a specific provider only if consistent vendor/price routing is a requirement.

## Verified facts vs assumptions

### Verified facts

- Docker and all five Compose services are running; Backend, Postgres, PHP, and HR web healthchecks pass.
- Backend and Frontend health URLs return HTTP 200.
- The running Backend uses `AI_PROVIDER=openrouter` and `deepseek/deepseek-v4.1-flash-1017`; Fake Provider is not selected.
- The OpenRouter key endpoint returned HTTP 200 and account metadata reports the stated free-tier and limit values.
- The model catalog lists the configured model and its modalities/metadata.
- Alembic revision was `026_github_evidence` both before and after startup.
- No inference call was made; no credentials or sensitive account identifiers were exposed.

### Limitations / not verified

- No model generation was attempted, so paid inference capability and response quality are not confirmed.
- The actual upstream provider serving a completion cannot be identified without a completion request; none was allowed.
- The frontend has no Compose healthcheck; its HTTP 200 response was checked directly instead.
- The key endpoint returned usage and limit metadata for this key. It does not establish the organization’s aggregate account balance beyond those returned fields.

## Sources

- OpenRouter public model catalog: https://openrouter.ai/api/v1/models
- OpenRouter current-key endpoint documentation (response includes `is_free_tier`, usage, limits; rate-limit metadata is deprecated): https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key
- OpenRouter pricing and billing: https://openrouter.ai/pricing
- OpenRouter provider routing: https://openrouter.ai/blog/insights/model-routing/

## Free-first policy implementation status — 2026-11-14

### Verified in source

- The backend now defaults to `AI_PROVIDER=openrouter` and `OPENROUTER_MODEL=openrouter/free`; Docker Compose also defaults away from Fake.
- All production-created OpenAI-compatible providers are guarded before each inference attempt. The AI settings verification route uses the same free-only guard.
- Paid DeepSeek, Soal, Ollama, unknown/unapproved models, nonzero/missing prices, noncanonical endpoints, and any paid-mode/nonzero-budget configuration fail closed before inference.
- PostgreSQL migration `027_ai_free_first` adds usage events, atomic shared quota counters, and a persistent cost-alert circuit breaker. UTC defaults are 15 global requests/minute, 40 global/day, 5 per user/minute, and 20 per user/day.
- No inference request was made as part of implementing or documenting this policy.

### Runtime status and blockers

- The previous runtime verification above observed `deepseek/deepseek-v4.1-flash-1017` in the running Backend. That paid model is now rejected by the source guard; the existing running container has not been rebuilt/recreated during this implementation, so the new guard is not yet active in that container.
- Migration `027_ai_free_first` has been created but not applied to the development database. Deploying the new backend before this migration will cause guarded inference to fail closed.
- To use free inference after deploying the migration, set `OPENROUTER_MODEL=openrouter/free` in the backend environment. Explicit free variants additionally require catalog verification and an `AI_FREE_MODEL_ALLOWLIST` entry.
- Backend suite result after implementation: 1,070 passed, 1 skipped, 12 deselected; all changed backend files pass targeted Ruff checks. A repository-wide Ruff scan still reports formatting/lint findings in untouched files. Migration SQL was generated offline only; it was not applied. Tests used the separate `hr_ai_assistant_test` database, not the application database. No runtime inference was attempted. The frontend was not changed or rebuilt.

## Runtime deployment verification — 2026-11-14

### Verified facts

- Docker Compose project `hr-ai-assistant` is running; Backend is `healthy` on port 8000. PostgreSQL and the existing named database volume were left intact; only the Backend image/container was rebuilt/recreated.
- Effective Backend settings: `AI_PROVIDER=openrouter`, `OPENROUTER_MODEL=openrouter/free`; an API key is present (value not recorded). Fake provider is not active.
- The Backend health endpoint returned HTTP 200.
- Database Alembic revision is `027_ai_free_first`; the Backend startup command applied the migration successfully.
- Authenticated `GET /api/v1/key` returned HTTP 200. The response reports Free-tier, a $2 limit, $0.147137533 usage, and $1.852862467 remaining. The deprecated rate-limit metadata was not used as a quota measure.
- Public OpenRouter catalog `GET /api/v1/models` returned `openrouter/free` (`Free Models Router`) with zero prompt/completion prices, text output, text/image input, and support for `response_format` and `structured_outputs`.
- No chat completion or other inference request was sent; no credits were spent by this verification.

### Assumptions and remaining limitations

- The free router may choose among eligible free upstream models; this check confirms the router configuration, not a specific upstream model or output quality.
- The current-key endpoint's usage/limit describes this API key and is not proof of an organization-wide balance.
- No inference was run to test model availability end-to-end. First inference remains subject to upstream free-model availability and application contract validation.

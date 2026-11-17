# HERA AI Cost Audit

**Audit date:** 2026-11-14  
**Scope:** Read-only review of the HERA recruitment app, AI-provider configuration, workflow call patterns, token accounting, and published provider prices.  
**Repository:** `HR-Project/HR create jop`  
**Constraints observed:** No files/configuration were changed except this report. No paid inference/API request was made. No secret values were read into the report or printed.

## Executive summary

- **The backend supports three live-compatible routes:** Ollama Cloud (`gemma4:31b`), OpenRouter (DeepSeek V4.1 Flash 1017), and the Soal gateway (configured model label `gemini-3.5-flash`). `FakeAIProvider` is also available for offline/test use.
- **The local backend `.env` selects Ollama Cloud**, with `OLLAMA_MODEL=gemma4:31b`. Credential-presence checks found values set for Ollama and OpenRouter, and no Soal key; this does not verify validity or available credits. OpenRouter is configured as an alternative. Secret values are intentionally omitted.
- **Docker’s effective provider cannot be assumed to match the backend `.env`:** `docker-compose.yml` explicitly overrides `AI_PROVIDER` from the Compose project environment and defaults it to `fake`. The project-root `.env` has no `AI_PROVIDER` entry, so an uncustomized `docker compose up` selects `fake`, even though `backend/.env` selects Ollama. Docker Engine was unavailable during this audit, so no running container setting could be verified.
- Cost estimates below are **AI inference only**. The app’s actual distribution of workflow types and usage logs were not available. Estimates use an explicit operation mix and token assumptions; replace them with `ai_traces.token_usage` aggregates before budgeting production.
- With the stated typical workload, an AI operation costs about **$0.0010 on OpenRouter DeepSeek** or **$0.00117 on Ollama Gemma 4** at the public rates observed on the audit date. A screening of one resume uses a profile extraction plus two evaluation calls (three model calls); it is therefore more expensive than a one-call action.
- Hosting, database, backups, object storage, outbound traffic, Apify, and human support costs are **not priced here** because the project only describes local Docker Compose; no cloud deployment/provider, region, resource plan, or production usage is specified.

## 1. Existing AI architecture and workflows

### Provider selection and configuration

| Provider | Code path | Inspected setting/default | Notes |
|---|---|---|---|
| Ollama Cloud | `app/ai/providers/ollama_cloud.py` → shared OpenAI-compatible adapter | `OLLAMA_BASE_URL=https://ollama.com/v1`; model default `gemma4:31b`; local `.env` selects `AI_PROVIDER=ollama` | Remote hosted inference; not local GPU inference. `OllamaCloudProvider` inherits the Soal adapter but uses the Ollama endpoint/model. |
| OpenRouter | `app/ai/providers/openrouter.py` → shared adapter | `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`; model `deepseek/deepseek-v4.1-flash-1017`; max output tokens default 4096 | Available when `AI_PROVIDER=openrouter` and key is set. |
| Soal | `app/ai/providers/soal.py` → shared adapter | `https://soal.help/api/v1`; model label `gemini-3.5-flash` | This is a Soal gateway, not a direct Google Gemini API integration. Do not apply Google’s direct API price to this route. A runtime API-key override can select Soal. |
| Fake | `app/ai/providers/fake.py` | Explicit `AI_PROVIDER=fake`; Compose fallback | Deterministic fake responses; no provider inference charge. Not a production substitute for real AI quality. |

All live providers use the OpenAI Python SDK through `OpenAICompatibleProvider`. The adapter has a 60-second timeout and SDK `max_retries=1`; structured requests use JSON mode when supported, retry transient provider errors/invalid JSON up to three outer attempts, and fall back without `response_format` when the provider rejects JSON mode. These retries can create extra billable calls. Provider responses can include input/output token usage. No application-side price is calculated at request time.

### AI workflow call count

| User operation | Approx. model calls | Notes |
|---|---:|---|
| Candidate profile extraction | 1 | Structured CV profile extraction. PDF/DOCX text extraction itself is local (`pypdf`/`python-docx`), with no OCR. |
| Screening one candidate | 2 | Evidence generation and explanation generation. Batch worker also runs candidate profile extraction if needed; a new manual-upload screening can therefore total 3 calls including extraction. |
| Job profile/JD extraction | 1 | Sends job description and schema/instructions. Long pasted/imported listings can materially increase input tokens. |
| HERA assistant turn | 2 | One structured plan call and one response composition call. History is bounded to at most 10 messages × 500 characters; composition is capped at 25,000 characters. Tool execution itself is internal and does not add a model call. |
| Interview question generation | 1 | Structured question output. |
| Job distribution/social post draft | 1 | Structured post draft. |
| GitHub evidence analysis | 1 | Sends gathered evidence to model; GitHub requests are a separate dependency. |
| AI job draft/improvement | 1 per action | Generate and suggest/improve endpoints each call the provider. |
| Provider “verify” action | 1 | A text-generation call; may incur a charge if it uses a paid provider. |

No embeddings/vector database or RAG pipeline was found in the inspected AI workflow surface. Resume parsing is local text extraction; scanned image PDFs are not OCR’d. Candidate/resume text is sent to the configured external AI provider for profile extraction and evaluation, so data-transfer/privacy policy is part of provider selection even though it is not a token-cost line item.

### Token and cost observability

`AITrace` stores provider/model, latency, and `token_usage` JSON per AI call when a provider returns usage. `WorkflowTraceService` persists these traces. It does **not** store calculated price, and usage can be absent from error/retry records. There was no running DB available to aggregate actual traces. Persisted usage is the best source for replacing the planning assumptions in this report:

`monthly AI cost = Σ(input_tokens × input_rate + output_tokens × output_rate + cache tokens × cache rate) / 1,000,000`

Count each provider attempt/retry, not only each successful user operation.

## 2. Provider pricing, free usage, and availability

### Published model rates (checked 2026-11-14)

| Configured route/model | Input / 1M | Cached input / 1M | Output / 1M | Billing interpretation |
|---|---:|---:|---:|---|
| OpenRouter `deepseek/deepseek-v4.1-flash-1017` | $0.038 | $0.010 | $0.50 | OpenRouter public model metadata reports these per-token rates. OpenRouter may route across providers; provider/routing conditions can affect actual invoice. |
| Ollama Cloud `gemma4` family | $0.14 | $0.05 | $0.40 | Ollama’s published pay-as-you-go model table. Local setting is `gemma4:31b`; confirm the API’s exact model alias and metering from usage dashboard before production budgeting. |
| Soal gateway, `gemini-3.5-flash` label | Unknown | Unknown | Unknown | No rate was assumed. This is not a direct Google Gemini API endpoint and the gateway’s billing terms/account are unavailable to this audit. |

Ollama advertises Pay-as-you-go with no subscription and metered model use; its listed Pro plan is $20/month with $60 of usage credits, and Max is $100/month with $300 of credits. These are account plan terms, not free unlimited inference. The exact applicable plan/credits for this project account were not inspected. OpenRouter’s paid model is not free. Its `:free` model variants are separately priced/limited and availability/rate limits can change; they are not an equivalent guaranteed production capacity tier.

### Account-specific note from earlier testing in this conversation

A previous authorized OpenRouter test in this project conversation observed the account’s credits endpoint at **$0 total credits** with nonzero prior usage, a paid DeepSeek test returning HTTP 402, and a free Cohere model completing a small request at no charge. This is historical evidence, not a fresh balance check. No account endpoint was queried during this audit, so the current credit balance is unknown. A successful free model response proves API connectivity for that model, not that paid credit is available or that HERA workflow quality is production-ready.

## 3. Estimated AI inference scenarios

These estimates model **30 days** and one counted operation per user action from the workflow list. They are not measured production usage and exclude retries, cache discounts, provider plan credits, and all non-AI infrastructure.

### Explicit planning assumptions

**Feature mix per counted AI operation:** 20% candidate profile extraction, 40% candidate screening (two calls), 10% job profile extraction, 15% HERA assistant turn (two calls), 5% interview questions, 4% job distribution, 4% GitHub evidence, and 2% job draft/improvement. This produces about **1.55 provider calls per operation**.

**Estimated aggregate tokens per operation:**

| Case | Input tokens | Output tokens | Reasoning |
|---|---:|---:|---|
| Low | 1,800 | 800 | Short CV/JD, brief outputs, limited workflow history. |
| Typical | 3,431 | 1,723 | Weighted feature mix above; moderate CV/JD and structured output. |
| High | 8,500 | 3,500 | Long CV/listing, larger evidence context/output, and more verbose structured results. |

Token counts are planning estimates derived from prompt/workflow shape, not tokenizer measurements. Long CVs, imported job descriptions, screening evidence, or repeated retries can exceed the high case. The context window is not the same as the amount the application sends: output is capped at 4,096 tokens for OpenRouter, while inputs vary by workflow.

### OpenRouter DeepSeek estimated monthly AI cost (USD)

Each cell is **low / typical / high** for the selected DAU and operations/day, using the OpenRouter rates above.

| DAU | 5 operations/day | 15 operations/day | 30 operations/day |
|---:|---:|---:|---:|
| 10 | $0.70 / $1.49 / $3.11 | $2.11 / $4.46 / $9.33 | $4.22 / $8.93 / $18.66 |
| 50 | $3.51 / $7.44 / $15.55 | $10.54 / $22.32 / $46.64 | $21.08 / $44.63 / $93.28 |
| 100 | $7.03 / $14.88 / $31.09 | $21.08 / $44.63 / $93.28 | $42.16 / $89.27 / $186.57 |
| 500 | $35.13 / $74.39 / $155.47 | $105.39 / $223.17 / $466.43 | $210.78 / $446.35 / $932.85 |
| 1,000 | $70.26 / $148.78 / $310.95 | $210.78 / $446.35 / $932.85 | $421.56 / $892.69 / $1,865.70 |
| 5,000 | $351.30 / $743.91 / $1,554.75 | $1,053.90 / $2,231.73 / $4,664.25 | $2,107.80 / $4,463.45 / $9,328.50 |


### Ollama Cloud Gemma 4 estimated monthly AI cost (USD)

Same workload and token assumptions, using Ollama’s published `gemma4` rates. Each cell is **low / typical / high**.

| DAU | 5 operations/day | 15 operations/day | 30 operations/day |
|---:|---:|---:|---:|
| 10 | $0.86 / $1.75 / $3.88 | $2.57 / $5.26 / $11.65 | $5.15 / $10.53 / $23.31 |
| 50 | $4.29 / $8.77 / $19.43 | $12.87 / $26.31 / $58.27 | $25.74 / $52.63 / $116.55 |
| 100 | $8.58 / $17.54 / $38.85 | $25.74 / $52.63 / $116.55 | $51.48 / $105.26 / $233.10 |
| 500 | $42.90 / $87.72 / $194.25 | $128.70 / $263.15 / $582.75 | $257.40 / $526.29 / $1,165.50 |
| 1,000 | $85.80 / $175.43 / $388.50 | $257.40 / $526.29 / $1,165.50 | $514.80 / $1,052.59 / $2,331.00 |
| 5,000 | $429.00 / $877.15 / $1,942.50 | $1,287.00 / $2,631.47 / $5,827.50 | $2,574.00 / $5,262.93 / $11,655.00 |


**Example reading:** at 100 DAU and 15 operations per user per day (45,000 operations/month), typical AI inference is approximately **$44.63/month on OpenRouter DeepSeek** or **$52.63/month on Ollama Gemma 4**. The high case is about $93.29 and $116.55 respectively. This is a planning comparison only; it excludes account-level terms and observed retries. The low/typical/high estimates scale linearly and should be recalculated from real `token_usage` telemetry after a representative pilot.

### System cost outside inference

| Cost item | Finding | Needed to price it |
|---|---|---|
| App/containers | Compose defines PostgreSQL, FastAPI backend, frontend, PHP HR Manager, and nginx HR web. This repo does not name a cloud vendor, instance size, region, HA plan, or production host. | Deployment target, region, instance sizing, uptime/replica requirements. |
| Database | PostgreSQL 16 with a named persistent Docker volume in the local Compose definition. | Managed/self-hosted plan, allocated storage, backup retention, IOPS, HA/replica needs. |
| Resume/document storage | Backend defaults to local `storage/`; no cloud object-storage integration/cost is specified in the inspected config. | Production storage choice, retained GB, egress, backup/versioning. |
| Network/egress | Not specified. Public job pages, CV files, and AI provider traffic may create egress charges. | Region, traffic, file-download patterns, CDN. |
| Apify | LinkedIn importer is integrated, actor ID is configured, and import is disabled by default. Actor usage is a separate metered vendor cost; no actor run was made for this audit. | Actor plan/price and number of imported listings. |
| Operations | Monitoring, logging retention, support, security, and engineering costs are not defined in Compose. | Service-level target and operations plan. |

**Can the application scale?** The code has an asynchronous PostgreSQL-backed screening worker and batch queue, and Compose has no replica/resource limits specified. This is a useful local/dev topology, not evidence of tested horizontal scaling. The current AI provider concurrency and worker throughput are bounded by provider account limits and application worker design. No load test, production DB, or live container was available; capacity at 500–5,000 DAU remains unverified. Budgeting must include the fixed hosting/DB/storage baseline separately from the variable inference table.

## 4. Configuration and deployment risk findings

1. **Local runtime vs Docker runtime can differ.** Local backend `.env` says `AI_PROVIDER=ollama`. Compose sets `AI_PROVIDER: ${AI_PROVIDER:-fake}`, which overrides values from `env_file`. The root `.env` had no `AI_PROVIDER` entry in the safe allow-listed inspection, so Compose’s default is `fake` unless an environment variable or project-root `.env` supplies another value. This can make local code appear to use a paid AI provider while the container silently uses fake responses.
2. **OpenRouter model configuration exists but is not the selected local provider.** Do not equate presence of an OpenRouter key with active OpenRouter usage. Provider factory chooses by `AI_PROVIDER` (or a runtime Soal key override); local selection is Ollama.
3. **Soal is a separate gateway.** The model string contains a Gemini-style name, but endpoint/billing are Soal; its rate and data terms must come from Soal’s account/docs, not Google pricing.
4. **Retry behavior affects costs.** Structured operations can reattempt transient failures or invalid JSON; the SDK has an additional retry allowance. Add per-attempt metrics and cost alerts before broad rollout.
5. **Provider credential presence is not balance.** Secret values were not revealed. Earlier OpenRouter account test indicates paid credits were unavailable then; the present balance was not checked.
6. **No external AI calls were made during this audit.** The only network pricing check was public, unauthenticated OpenRouter model metadata; no API key was used.

## 5. Free-tier and provider comparison

| Option | Strength | Cost/limits | HERA fit and caveat |
|---|---|---|---|
| Ollama Cloud Gemma 4 | Current local `.env` selection; published per-token cost and a no-subscription pay-as-you-go plan | Metered input/output; account has concurrency/credit rules. | HERA uses OpenAI-compatible JSON mode. Validate structured-output behavior and exact `gemma4:31b` alias with synthetic CVs; do not assume the general Gemma page guarantees every adapter behavior. |
| OpenRouter DeepSeek V4.1 Flash 1017 | Current configured OpenRouter alternative; low published input price and large context; public model metadata advertises `response_format`/structured output support | Paid tokens; free models have separate variable limits. The prior account test got HTTP 402. | The adapter sends JSON mode and supports 4096 output tokens. This report does not establish current balance or guarantee provider availability. |
| Soal gateway | Existing compatible provider integration | Price and included credits unknown to this audit; local key absent. | Obtain Soal’s pricing, privacy/retention, and quota terms. Do not quote direct Google Gemini rates for this route. |
| Fake provider | No inference cost, stable offline tests | Not intelligent and not a user-facing AI quality option. | Appropriate only for tests/demo fallback that is clearly labeled. |
| Direct Gemini API | Google publishes a separate price schedule | Not currently the configured endpoint/provider. | Would be a provider change; not included in the current cost forecast. |

## 6. Cost control and quality recommendations

1. **First make provider selection explicit.** In each run environment, verify the effective provider/model in the backend’s safe AI settings status or startup diagnostics. Avoid a Compose default that silently changes paid-vs-fake behavior; handle that as a separate approved configuration change.
2. **Collect per-call usage.** Aggregate successful `AITrace.token_usage` by organization/workflow/provider/model and include failed/retried attempts. Add price-table versioning and calculated estimated USD without storing raw prompts/CVs in metrics.
3. **Set budgets and alerts at the provider account.** Use OpenRouter/Ollama spend limits where available, plus application-side per-org/month and per-user rate limits. Alert on unusual screening batch size and retries.
4. **Reduce repeated context.** Bound imported JDs/CV text and assistant history; trim irrelevant boilerplate before calls while preserving the source record; avoid including the same requirement/profile text in both evaluation calls where contract quality permits.
5. **Use deterministic/local work for mechanical tasks.** Keep PDF/DOCX extraction, schema validation, requirement checks, scoring, and verification in code. This is already partly reflected in HERA; do not move deterministic scoring to an LLM for convenience.
6. **Tune retries.** Keep retryability for 429/5xx, but limit attempts, honor `Retry-After` if supported, and avoid repeating a paid call for content/contract validation errors that prompt fixes can address.
7. **Run a synthetic benchmark before production.** Use consent-free synthetic CV/JD pairs, blind rubric scoring, factuality checks, and HR review. Compare completion rate, latency, malformed-JSON rate, evidence precision/recall, cost per screened candidate, and cost per successful job profile across providers. Do not send real candidate CVs until provider privacy/retention is approved.
8. **Keep HR approval and screening controls.** The model is advisory; HR approval before screening remains part of the product workflow. Cost optimization must not change the scoring algorithm or remove human review.

## 7. Unknowns / data needed for a production budget

- Actual DAU and the distribution of AI operations per user.
- Actual `token_usage` percentiles and retries by workflow/model, including long-tail CV/JD lengths.
- Whether current production container uses Ollama, OpenRouter, Soal, or Fake; Docker was unavailable at audit time.
- Actual OpenRouter/Ollama account balances, credit plans, spend caps, and provider-specific routing prices. These were not checked with credentials.
- Soal rate card, quota, retention, region, and whether its Gemini-labeled model bills by token or another unit.
- Deployment vendor/region, CPU/RAM, replica/HA needs, database/storage size and retention, backup/egress costs.
- Apify plan and expected LinkedIn import volume.
- Whether organizations need hard monthly AI spend caps and cost allocation.

## 8. Files reviewed

- `HR create jop/backend/app/ai/providers/factory.py`
- `HR create jop/backend/app/ai/providers/openai_compatible.py`
- `HR create jop/backend/app/ai/providers/openrouter.py`
- `HR create jop/backend/app/ai/providers/ollama_cloud.py`
- `HR create jop/backend/app/ai/providers/soal.py`
- `HR create jop/backend/app/ai/workflows/` (candidate profile extraction, candidate evaluation, job profile extraction, interview questions, HERA assistant)
- `HR create jop/backend/app/services/job_distribution_service.py`
- `HR create jop/backend/app/services/github_evidence_service.py`
- `HR create jop/backend/app/services/workflow_trace_service.py`
- `HR create jop/backend/app/models/ai_trace.py`
- `HR create jop/backend/app/services/text_extraction_service.py`
- `HR create jop/backend/app/worker.py`
- `HR create jop/backend/app/core/config.py`
- `HR create jop/backend/.env` (only allow-listed non-secret setting names/values and secret-presence booleans inspected)
- `HR create jop/backend/.env.example`
- `HR create jop/docker-compose.yml`

## 9. Official pricing and technical references

- OpenRouter model page and price/context/capabilities: https://openrouter.ai/deepseek/deepseek-v4.1-flash-1017
- OpenRouter public model metadata endpoint: https://openrouter.ai/api/v1/models (unauthenticated catalog; no generation request)
- OpenRouter credits API documentation: https://openrouter.ai/docs/api/api-reference/credits/get-credits
- OpenRouter FAQ on credits, model pricing, and free model limits: https://openrouter.ai/docs/faq
- Ollama public pricing, plans, model rates, concurrency, and privacy statements: https://ollama.com/pricing
- Ollama Gemma 4 model page: https://ollama.com/library/gemma4:cloud
- Google Gemini API pricing (reference only; does not price the Soal gateway): https://ai.google.dev/gemini-api/docs/pricing

---

**Audit conclusion:** HERA has a usable provider abstraction and token-usage trace fields, but a defensible total monthly product cost cannot be stated until the effective deployed provider is verified, real workflow token usage is aggregated, and hosting/vendor plans are identified. Under the explicit planning assumptions in this report, inference is inexpensive per operation; infrastructure and the active vendor account/plan are the main missing budget inputs.

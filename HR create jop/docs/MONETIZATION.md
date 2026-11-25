# HERA Monetization & Subscriptions

Status: **v1 shipped (manual billing mode)** — additive only; no changes to screening,
scoring, or HR decision logic, and no plan limit is enforced on existing flows yet.

## Goals

1. A plan catalog and per-organization subscription state that the product and UI can rely on.
2. A pricing page and in-app billing surface so an org admin can see plans, their current
   plan, and usage against limits.
3. A clearly marked integration point where a payment provider (Stripe recommended) attaches
   without reworking the domain model.

## Plan catalog (v1)

| Code | Name | Price (USD/mo) | Active jobs | Screenings/mo | Seats | Extras |
| --- | --- | --- | --- | --- | --- | --- |
| `free` | Starter | 0 | 3 | 50 | 2 | Talent pool, interview scheduling |
| `pro` | Pro | 49 | 25 | 1,000 | 10 | + OCR CV intake, priority support |
| `business` | Business | 199 | unlimited | 10,000 | unlimited | + audit exports, dedicated support |

Limits are numeric caps (`-1` = unlimited) stored on the plan row; feature flags live
alongside them. The catalog is seeded idempotently by `SubscriptionService.ensure_default_plans`
(code is source of truth; existing rows are not mutated).

## Domain model

- `plans` — catalog rows (code, name, price, currency, limits JSON, features JSON, status).
- `organization_subscriptions` — one row per organization (unique on `organization_id`):
  plan FK, status (`trialing` / `active` / `past_due` / `canceled`), `provider`,
  `provider_customer_id`, `provider_subscription_id`, period start/end, `cancel_at_period_end`.

Organizations are auto-provisioned onto `free` on first read, so every org always has a
well-defined plan and the UI never handles a missing-subscription case.

## Billing providers and the integration point

`provider` records who bills the subscription:

- `none` — free tier, no billing.
- `manual` — **v1 behavior for paid tiers.** An admin switches plans in the UI and the
  subscription activates immediately; invoicing happens outside the product. This keeps
  monetization usable before any payment provider account exists.
- `stripe` (future) — set by the provider sync once integrated.

### Attaching Stripe later (planned flow)

1. `POST /billing/subscription/checkout` (new) creates a Stripe Checkout Session for the
   selected plan and returns the redirect URL. The current change-plan endpoint keeps
   working for `manual` mode and tests.
2. Stripe webhook (`POST /billing/webhooks/stripe`, signature-verified) maps
   `customer.subscription.*` events onto `organization_subscriptions`: sets `provider`,
   `provider_customer_id`, `provider_subscription_id`, status transitions
   (`active` / `past_due` / `canceled`) and period dates.
3. Plan switching stays idempotent; `billing.plan_changed` audit events already capture
   from/to plan and provider for every change.

## API (all org-scoped, recruiter+admin read; plan change admin-only)

- `GET /api/v1/billing/plans` — active catalog.
- `GET /api/v1/billing/subscription` — current subscription (auto-provisions free tier).
- `POST /api/v1/billing/subscription/plan` — `{plan_code}` switch; returns `checkout: "manual"`
  until a provider exists.
- `GET /api/v1/billing/usage` — usage meters vs limits: `active_jobs`,
  `screenings_per_month` (evaluations this calendar month), `seats`.

## Enforcement strategy (not in v1)

v1 deliberately only *exposes* limits and usage. When enforcement is switched on, it should
happen at the edge (job activation, screening batch start, user invite) by reading
`SubscriptionService` — never inside scoring or decision logic. Recommended order:

1. Soft warnings in the UI at 80% of any meter (data already available from `/billing/usage`).
2. Hard caps on `active_jobs` and `seats` (simple counts, easy to explain to customers).
3. `screenings_per_month` cap with an automatic grace buffer (e.g. 10% overage) to avoid
   cutting off an in-flight hiring round.
4. Feature gates (`ocr_cv_intake`, `audit_exports`) via the plan's `features` map.

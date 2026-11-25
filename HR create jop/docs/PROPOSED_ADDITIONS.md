# HERA — Prioritized Additions Proposal

Source: read-through of `docs/roadmap.md`, `docs/product-requirements.md`,
`ARCHITECTURE.md`, `docs/notes/phases_roadmap.txt`, plus the 2026-11-25 work on
billing and OCR. Ordered by value vs. effort and by what unlocks revenue first.
Boundaries respected throughout: no autonomous hiring/rejection, no scoring-formula
changes without approval, no LinkedIn scraping, human review stays authoritative.

## P0 — Unlocks revenue or production

1. **Payment provider integration (Stripe) for the new billing system.**
   The v1 subscription model, plan catalog, usage meters, and Billing UI are in
   place (manual mode). The integration point is documented in
   `docs/MONETIZATION.md`: checkout-session endpoint + signed webhook writing
   `provider_customer_id` / `provider_subscription_id`. Without this, paid plans
   stay invoiced-by-hand.
2. **Plan-limit enforcement at the edges.**
   v1 exposes limits; nothing enforces them. Recommended order (also in
   MONETIZATION.md): UI soft warnings at 80% → hard caps on `active_jobs` and
   `seats` → `screenings_per_month` with a small grace buffer → feature gates
   (`ocr_cv_intake`, `audit_exports`). All checks live at API edges via
   `SubscriptionService`; scoring and decision logic untouched.
3. **Production AI provider config.**
   Live screening currently depends on an OpenRouter key that exists only on the
   developer machine (per `hrezzlatestupdate.md`: free model +
   `OPENROUTER_MAX_TOKENS=4096` to stay inside credit). Production needs: key in
   deployment env, a paid-model decision vs. the free-first cost policy, and
   credit/budget alerting on top of the existing AI usage metering.
4. **Arabic OCR pack.**
   OCR CV intake ships with English tesseract data. Installing the `ara`
   traineddata pack and setting `OCR_LANGUAGES=eng+ara` covers Arabic CVs —
   high value for the Egyptian/Gulf market, one-line config once the pack is on
   the host image.

## P1 — Completes the candidate side (roadmap: "Partial")

5. **Candidate portal completion.** Invitation + scheduling + consent APIs exist;
   the self-service experience (status visibility, reschedule, document
   re-upload, withdrawal) is the gap. Highest product polish per effort because
   the backend is already built and tested.
6. **HR-reviewed candidate communications.** Roadmap marks this "not implemented"
   and requires human authorization for any send. Start with review-then-send
   status emails (advance / hold / reject / interview invite) rendered from
   templates, logged to the audit trail, sent only on explicit HR click.
   Transactional email outbox model already exists to build on.
7. **Licensed sourcing switchover.** Dev sourcing uses Apify actors under a
   no-login/public-index constraint. Before revenue: move to a licensed provider
   (Coresignal recommended), keep the org-scoped record → start run → poll →
   read dataset pattern, and purge dev-sourced data at switchover.

## P2 — Deepens the HR side

8. **Plan-aware audit exports (Business tier).** Audit logs exist; a filtered
   CSV/JSON export endpoint is small, and it is already a Business feature flag.
9. **Interview scorecard → evaluation feedback loop.** Feedback learning
   analytics exist (corrections tracked). Surface per-requirement "AI said /
   HR decided" drift on the analytics page to support future weighting
   suggestions — suggestions only, HR approves any rule change per the PRD.
10. **Onboarding/employee lifecycle discovery.** Roadmap: not implemented, scope
    undefined. Run the requirements pass first (data model + lifecycle states)
    before any schema work; it is the largest greenfield area and easy to
    over-build.

## Explicitly deferred

- **HR digest / morning briefings** — design-only note; not to be built yet.
- **Autonomous anything in decisions** — excluded by the PRD permanently.
- **External ATS / LinkedIn sync** — only official, permissioned integrations;
  revisit after the licensed sourcing switchover (P1-7).

# HERA UI and Data-Integrity Audit Backlog

Read-only source audit of the supplied UI observations. Screenshot claims were
treated as hypotheses and checked against the canonical app at
`frontend/frontend_last/` and its current backend contracts. This backlog does
not authorize implementation. Preserve the existing local working-tree changes
when taking up any item.

## Priority 0 — data correctness and trust

### P0.1 Format application scores without changing their meaning

- **Finding: confirmed.** `GET /job-applications` returns `score` as a nullable
  string. `ApplicationsList.jsx` appends `%` to that raw string, so values such
  as `95.000` retain trailing precision and exponent-form Decimal strings would
  be rendered literally. The API read model intentionally exposes the score as
  a string. The scoring service documents and computes a 0–100 Decimal score,
  quantized to three decimal places. `CandidateEvaluation.score` is stored as a
  generic numeric column, so the schema itself does not enforce that range or
  precision for historical/manual values.
- **Data limitation:** no database score samples were read during this audit;
  the implementation follow-up inspected aggregate local current-evaluation
  values only: 2 scores, min 0, max 81.579, and 0 outside 0–100. The scoring
  service independently documents that scale. Display formatting now accepts
  decimal and exponent strings, shows at most one decimal, and treats malformed
  or out-of-range values as unavailable. Numeric service values remain
  unrounded for sorting; API contracts and scoring are unchanged.
- **Affected screens:** Applications, candidate review, matching results, and
  analytics score metrics.
- **Implementation status:** fixed in the shared score parser/formatter and
  Applications, review, evaluation, ranked, candidate, matching, and talent
  pool score consumers. Tests cover numeric strings, exponent notation, zero,
  precision, malformed values, and range rejection.
- **Likely regression risks:** changing the API string contract, changing the
  0–100 scale, altering sort/filter comparisons, or presenting a rounded value
  as the underlying score. These remain guarded by the display-only formatter
  and unrounded numeric service values.

### P0.2 Make analytics counts and percentages truthful

- **Finding: confirmed.** Analytics labels the view “Last 30 days” but fetches
  all organization applications and active jobs without a date filter.
  The displayed stage percentage divides each status count by the maximum
  status count, not by a cohort or prior stage. Thus Applied = 1 and Advanced =
  1 both become 100%; these are relative bar widths, not conversion rates.
  The statuses are mutually exclusive counts, not cumulative funnel stages.
- **Additional issue:** `applicationService` preserves `row.score` as a string,
  but `analyticsService.avgScore` only accepts JavaScript numbers, so the
  average AI score is omitted for the current API response shape.
- **Affected screens:** Analytics and any dashboard funnel visualization.
- **Implementation status:** Analytics now filters application creation
  timestamps to the rolling prior 30×24 hours (inclusive of the exact lower
  bound and current instant), labels the status view as a current snapshot,
  divides status counts by in-period application total, includes archived and
  unknown statuses, and removes the unsupported advance-rate claim. Average
  scores accept valid API numeric strings. Active jobs are explicitly labeled
  as a current count; candidate sources say they are not collected.
- **Likely regression risks:** miscounting historical applications or
  presenting a period claim without applying the date window. Boundary,
  empty-window, equal/different-count, unknown-status, and string-score tests
  cover the chosen definitions.

### P0.3 Keep candidate, application, and hiring metrics distinct

- **Implementation status:** Dashboard now labels the first KPI **Candidates
  with applications** (distinct candidate IDs with at least one application),
  and the forward-state KPI **Advanced applications** (application rows whose
  current status is `advanced`). Active jobs remains a current job count.
  Internal KPI properties now use the same entity names. No Hired metric is
  inferred from the available status vocabulary.
- **Affected screens:** Dashboard and Analytics.
- **Likely regression risks:** silently changing KPI definitions, counting
  candidates where applications are intended (or vice versa), or introducing
  a “Hired” state without a source-of-truth status. Before future KPI changes,
  define each metric’s entity, population (including whether candidates with
  no applications count), status set, and denominator.

### P0.4 Prevent unrelated resume sections from appearing as certifications

- **Finding: extraction risk confirmed; the reported candidate row is not
  independently verified.** The deterministic extractor’s `_CERT_RE` matches
  `professional` followed by up to 100 characters on the same line. It can
  therefore return headings such as “PROFESSIONAL EXPERIENCE” or
  “PROFESSIONAL SUMMARY” as certification strings. The candidate-profile
  contract keeps `summary`, `experience`, and `certifications` as distinct
  fields, but does not semantically validate their contents. The review page
  renders `profile_data.certifications` verbatim.
- **Affected screens:** Candidate Review and Candidate Details.
- **Likely regression risks:** suppressing a legitimate certification that
  contains “professional,” dropping valid source text, or changing extracted
  profiles used for evaluation. Fix the extraction classification with
  section-aware tests against realistic CV text and ensure invalid heading
  values are not presented as certifications. Do not rewrite stored profile
  history silently.
- **Implementation status:** extractor now honors explicit certifications or
  licenses sections, stops at the next recognized resume section heading, and
  rejects heading-only fallback matches such as PROFESSIONAL SUMMARY/EXPERIENCE.
  Candidate Review also filters heading-only strings from already-stored profile
  snapshots at display time without mutating profile history.
  Tests cover valid named certificates, a valid "Professional Scrum Master"
  credential, empty sections, misleading headings, section boundaries, and
  keyword-based credentials without a section. No stored profile was changed.

### P0.5 Keep AI assessment separate from the HR decision

- **Finding: distinction exists in code, presentation still merits review.**
  Application Review uses “Candidate Group” for the AI band (for example,
  “Must Review”) and “HR Decision” for the recorded human action. The separate
  `DecisionBar` calls the control “Human Hiring Decision” and says HR is final.
  The page also repeats the current decision in the status strip and profile
  panel. Source inspection confirms separate fields; authenticated visual
  inspection was unavailable.
- **Affected screens:** Application Review and Matching Results.
- **Likely regression risks:** merging AI group and HR decision states,
  implying that a model recommendation is an HR decision, or reducing the
  prominence/accessibility of the human action. If refined, keep distinct
  labels, placement, semantic colors, and the existing decision API.

## Priority 1 — workflow usability

### P1.1 Make one sidebar destination active at a time

- **Finding: confirmed route-matching risk.** Sidebar `NavLink`s omit `end`.
  Prefix matching can activate both `/candidates` and `/candidates/screen`, or
  `/interviews` and `/interviews/schedule`. Exact route matching is likely
  appropriate for these destinations; if hierarchy is intentional, define a
  visibly distinct parent/child state.
- **Affected screens:** every nested route with a sidebar parent.
- **Likely regression risks:** losing useful parent context, changing direct
  navigation, or making active states inaccessible. Cover nested and exact
  routes with navigation tests.
- **Stage 2A status:** fixed for the sidebar destinations by exact route
  matching (`NavLink end`). Parent navigation remains available; only the exact
  destination is visually active. Nested-route tests cover the previously
  ambiguous candidates and screening paths.

### P1.2 Improve Application Review hierarchy without obscuring evidence

- **Finding: mixed.** Candidate identity and status appear before the profile
  and evidence; the HR DecisionBar is rendered after the evidence section.
  No `position: sticky` rule was found for the decision bar, so the reported
  overlay concern is not confirmed. The late action placement may require
  scrolling; visual usability remains unverified because the browser stopped
  at sign-in.
- **Affected screens:** Application Review.
- **Likely regression risks:** hiding evidence, covering content, weakening
  keyboard order, or moving the final HR decision away from its context. Review
  authenticated desktop and narrow-width renders before changing layout.
- **Stage 2A status:** identity and job context are now surfaced first; AI
  review category, application state, and the human HR decision have distinct
  labels and presentation. A keyboard-accessible jump link moves focus to the
  existing decision controls. Evidence and decision APIs remain intact. The
  authenticated visual review remains pending because local sign-in did not
  complete.

### P1.3 Separate processing-state filters from HR decisions

- **Finding: confirmed.** Applications presents one flat status filter set
  containing processing states (`created`, `analyzing`, `ready_for_review`)
  and human decision states (`hold`, `advanced`, `rejected`). Matching Results
  also filters by application status. The screens have different purposes but
  the shared status vocabulary is not explained at the filter level.
- **Affected screens:** Applications, Matching Results, Screening, Candidates.
- **Likely regression risks:** changing server filtering, losing URL/query
  state, or confusing “candidate” records with “applications.” Group controls
  visually and label each workflow’s purpose without changing API contracts.
- **Stage 2A status:** Applications now groups filters under Processing,
  HR decision, and Other status. Selection still sends the same exact status
  query value to the existing API. The existing matching and screening routes
  are unchanged. The backend-provided AI review `group` is now preserved by the
  frontend service and shown in a separate table column; missing categories
  render as unavailable.

### P1.4 Distinguish zero results from unavailable source data

- **Finding: confirmed in Analytics; otherwise screen-specific review needed.**
  `getCandidateSources()` always returns an empty array because the backend has
  no source data. Analytics still renders the donut/legend shell with a total
  of zero, which can look like a genuine zero-source metric. The dashboard now
  separates its no-application state from request failure, but other empty
  states vary and should be audited by source capability.
- **Affected screens:** Analytics, Applications, Candidates, Talent Pool,
  Interview questions, and other list pages.
- **Likely regression risks:** presenting unsupported data as zero, hiding
  network errors, or offering actions the user cannot take. Model “not
  collected,” “no records,” and “request failed” as distinct states.
- **Stage 2B status:** Candidate Sources already renders the unsupported
  capability as “Source attribution is not collected”; its service returns
  `null` because no source endpoint/data exists. This is not a zero count. The
  remaining approved work refines true-empty versus filter-empty states on
  Interviews, Applications, and Candidates without changing their APIs.

### P1.5 Explain AI auto-fill behavior before use

- **Finding: mostly addressed in current code.** `JobForm` only applies HERA
  suggestions to fields considered empty, marks suggested fields, keeps them
  editable, and states that suggestions are not saved until Save is clicked.
  The primary button remains “Fill with HERA”; the no-overwrite behavior is
  explained after the action, rather than directly beside the button.
- **Affected screens:** Create Job and Edit Job.
- **Likely regression risks:** overwriting recruiter input, changing edit-form
  values, or suggesting fields with no source basis. Keep the empty-only merge
  and add pre-action explanation/tests if the flow is refined.
- **Stage 2B status:** approved for clearer pre-action copy and safe merging
  against current form values. The audit confirmed that edits made during the
  asynchronous suggestion request can currently be overwritten, and the
  default Full-time value cannot be distinguished from a user selection. The
  implementation must preserve edits made before and during generation.

## Audit boundary

- The original audit was read-only. This approved follow-up implemented the
  confirmed Priority 0 fixes above; it did not change API contracts, schemas,
  authorization, or stored candidate/profile records.
- Candidate-specific screenshot records were not queried. Authenticated browser
  verification was used to inspect the Dashboard, Analytics, and Applications
  screens with live aggregate/list data.
- No database records were modified. The authenticated application table was
  viewed only to verify score formatting; candidate profiles and decisions
  were not opened or changed.
- No commit was created. Existing unrelated working-tree changes were preserved.
- Stage 2A implements the approved Applications, Application Review, and
  sidebar usability items P1.1–P1.3. Stage 2B implements the approved empty
  state and job auto-fill UX items in P1.4–P1.5. Other routes remain
  backlog-only. No commit was created; existing unrelated working-tree changes
  were preserved.

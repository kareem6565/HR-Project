# HERA UI Design Direction

## Product direction

HERA is a focused hiring workspace for HR teams. Its interface should feel calm,
capable, and human while keeping candidate evidence and recruiter decisions easy
to scan. Use the **Editorial Hiring Command Center** direction: a warm, quiet
canvas around clear white work surfaces, structured typography, and compact but
readable data visualization.

## Brand foundation

| Role | Token | Value |
| --- | --- | --- |
| Deep brand | `--hera-teal-deep` | `#082A24` |
| Primary brand | `--hera-teal` | `#1B3A3A` |
| Page canvas | `--hera-cream` | `#F5EFE2` |
| Soft canvas | `--hera-cream-subtle` | `#FAF7F2` |
| Work surface | `--hera-surface` | `#FFFFFF` |
| Warm accent | `--hera-gold` | `#E9D98A` |
| Cool accent | `--hera-sky` | `#6FA8B8` |
| Body text | `--hera-ink` | `#292C2A` |

Use teal for navigation, primary actions, and important data marks. Gold and sky
blue are accents, not competing status systems. Evidence and decision states
retain their dedicated semantic colors and readable text labels.

## Interface principles

- Give each page one clear title, a short context line, then its primary work.
- Prefer readable tables, filters, and evidence details over ornamental cards.
- Use cards when they group meaningful information; keep surfaces quiet and
  shadows subtle.
- Use consistent spacing, visible keyboard focus, descriptive control labels,
  reduced-motion support, and responsive layouts.
- Let Arabic and English content wrap naturally and set direction per content
  where mixed-language layouts require it.
- Label derived figures and never imply unsupported API data exists.
- Show useful loading, empty, and error states with clear next steps.

## Stage 1 dashboard rules

- Show only live or transparently derived jobs and application totals.
- Call the deepest current workflow state **Advanced**; the dashboard service
  does not record a completed hire.
- Describe status counts as a distribution, not a conversion funnel: statuses
  are independent application states and are not cumulative stage totals.
- Use a single-brand chart palette and keep category labels visible.

## Visual directions considered

1. **Editorial Hiring Command Center** — spacious, readable, warm, and data-first.
   Selected because it balances HERA's approachable identity with evidence-heavy
   recruiting work.
2. **Teal Operations Console** — dense, utilitarian, and efficient for frequent
   operators; risks feeling heavy and harder to scan.
3. **Warm Human-Centered Workspace** — softer and more expressive; risks letting
   decoration compete with candidate evidence and decisions.

## UI/UX Pro Max guidance

The local design-system search suggested a data-dense dashboard and flat visual
style, with accessibility, keyboard use, focus visibility, reduced motion, and
responsive checks. Its generic palettes and type pairing do not match HERA's
existing brand tokens, so the repository's approved teal/cream palette and
current typography remain authoritative.

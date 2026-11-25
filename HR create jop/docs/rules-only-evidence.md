# Rules-only candidate evaluation

Set `AI_MODE=rules` to evaluate requirements with HERA's deterministic CV text
matching and evidence verification. The default, `AI_MODE=llm`, remains the
existing provider-backed flow.

Rules mode does not call an AI model. A requirement can contribute as matched
only when its quote is verified against the extracted CV text by
`EvidenceVerificationService`; uncertain evidence remains partial or missing.
The existing deterministic scoring and human hiring decision process remain in
place. Evaluations record `ai_mode=rules` and `generation_engine=rules_v1`, and
use a separate cache identity from provider-backed results.

Keyword matching can miss equivalent wording or context. HR should review the
quoted source evidence and the CV before recording any hiring decision.

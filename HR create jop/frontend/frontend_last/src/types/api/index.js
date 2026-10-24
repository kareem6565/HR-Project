// HERA backend API contract layer (Phase C).
//
// Everything the frontend needs to know about the backend API lives here:
// response shapes, request payloads, valid enums/statuses, and the complete
// endpoint catalog. Field names EXACTLY match the backend (snake_case) —
// see each file's header for its source-of-truth schema.
//
// Conventions:
//  - No runtime validation: contracts are expressed as JSDoc typedefs plus
//    frozen const enums so later phases (and IDEs) share one source of truth.
//  - Scores (`score`) are STRINGS in responses (e.g. "85.000"). The frontend
//    must never compute scores or groups.
//  - Lists are bare arrays; entities are bare objects. No `{ data: ... }`
//    envelope exists.
//  - Identity is header-based (X-User-Id / X-Organization-Id), set centrally
//    by the Phase B apiClient. No tokens.

export * from "./common.js";
export * from "./organization.js";
export * from "./user.js";
export * from "./job.js";
export * from "./jobProfile.js";
export * from "./candidate.js";
export * from "./resume.js";
export * from "./application.js";
export * from "./evaluation.js";
export * from "./matchEvidence.js";
export * from "./decision.js";
export * from "./workflow.js";
export * from "./aiSettings.js";
export * from "./endpoints.js";
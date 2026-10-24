// MatchEvidence (evaluation evidence) API contract.
// Source of truth: backend/app/api/v1/schemas/match_evidence.py and
// backend/app/models/match_evidence.py (evidence_type CHECK constraint).

/**
 * Valid values for `MatchEvidenceResponse.evidence_type`.
 * @typedef {"matched" | "missing" | "partial"} MatchEvidenceTypeValue
 */

/** DB-backed evidence-type vocabulary. */
export const MatchEvidenceType = Object.freeze({
  MATCHED: "matched",
  MISSING: "missing",
  PARTIAL: "partial",
});

/**
 * Response for `GET /api/v1/evaluations/{evaluation_id}/evidence`.
 * `requirement_ref` and `candidate_evidence` are opaque JSONB owned by the
 * evaluation workflow; their internal schema is not part of this contract.
 *
 * @typedef {object} MatchEvidenceResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} candidate_evaluation_id
 * @property {MatchEvidenceTypeValue} evidence_type
 * @property {import("./common.js").JsonObject} [requirement_ref]
 * @property {import("./common.js").JsonObject} [candidate_evidence]
 * @property {string} [strength]
 * @property {import("./common.js").JsonObject} [provenance]
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * MatchEvidence is a read-only sub-resource of an evaluation: the only
 * operation is the evidence list endpoint above.
 * @type {readonly ["listByEvaluation"]}
 */
export const MATCH_EVIDENCE_OPERATIONS = Object.freeze(["listByEvaluation"]);
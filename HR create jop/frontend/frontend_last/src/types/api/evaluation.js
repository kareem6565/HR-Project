// CandidateEvaluation API contract.
// Source of truth: backend/app/api/v1/schemas/evaluations.py and
// backend/app/models/candidate_evaluation.py (status CHECK constraint).

/**
 * Valid values for `CandidateEvaluationResponse.status`.
 * @typedef {"queued" | "running" | "completed" | "failed" | "superseded"}
 *   CandidateEvaluationStatusValue
 */

/** DB-backed status vocabulary. */
export const CandidateEvaluationStatus = Object.freeze({
  QUEUED: "queued",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
  SUPERSEDED: "superseded",
});

/**
 * Response for evaluation get / list.
 *
 * AMBIGUITY NOTE: `score` is serialized as a STRING (e.g. "85.000"); the
 * backend stringifies the numeric Decimal column in the response schema.
 * The frontend must treat score as a string and must never compute or
 * re-derive it. The AI recommendation/explanation shapes are opaque.
 *
 * @typedef {object} CandidateEvaluationResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} job_application_id
 * @property {import("./common.js").UUID} job_profile_id
 * @property {import("./common.js").UUID} candidate_profile_id
 * @property {number} version_number
 * @property {CandidateEvaluationStatusValue} status
 * @property {string} [score]
 * @property {string} [recommendation]
 * @property {import("./common.js").JsonObject} [explanation]
 * @property {import("./common.js").JsonObject} [score_breakdown]
 * @property {string} [scoring_version]
 * @property {import("./common.js").JsonObject} [provenance]
 * @property {boolean} is_current
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * CandidateEvaluation-supported API operations in the current backend.
 * @type {readonly ["get", "listByJobApplication"]}
 */
export const EVALUATION_OPERATIONS = Object.freeze([
  "get",
  "listByJobApplication",
]);
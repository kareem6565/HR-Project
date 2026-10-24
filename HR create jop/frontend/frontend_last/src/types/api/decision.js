// HRDecision API contract.
// Source of truth: backend/app/api/v1/schemas/hr_decisions.py and
// backend/app/models/hr_decision.py + decision_service (decision CHECK
// constraint: 'advance' | 'reject' | 'hold').

/**
 * Valid values for `HRDecisionCreate.decision` / `HRDecisionResponse.decision`.
 * @typedef {"advance" | "reject" | "hold"} HRDecisionValue
 */

/** Authoritative decision vocabulary. AI must never decide; HR does. */
export const HRDecisionValue = Object.freeze({
  ADVANCE: "advance",
  REJECT: "reject",
  HOLD: "hold",
});

/**
 * Request body for `POST /api/v1/job-applications/{application_id}/decisions`.
 * @typedef {object} HRDecisionCreate
 * @property {HRDecisionValue} decision
 * @property {string} [reason]
 */

/**
 * Response for `POST /api/v1/job-applications/{application_id}/decisions`.
 * @typedef {object} HRDecisionResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} job_application_id
 * @property {import("./common.js").UUID} user_id
 * @property {import("./common.js").UUID} [candidate_evaluation_id]
 * @property {HRDecisionValue} decision
 * @property {string} [reason]
 * @property {import("./common.js").ISO8601DateTime} created_at
 */

/**
 * AMBIGUITY NOTE: the decision SERVICE accepts an optional
 * `candidate_evaluation_id`, but the HTTP route does NOT expose it — the
 * create request payload is only `{ decision, reason }`. The backend also has
 * NO decision list endpoint; decisions are read back through the candidate
 * pool summary (`JobCandidateSummary.decision`).
 *
 * @type {readonly ["create"]}
 */
export const HR_DECISION_OPERATIONS = Object.freeze(["create"]);
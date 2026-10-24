// JobApplication API contract.
// Source of truth: backend/app/api/v1/schemas/job_applications.py and
// backend/app/models/job_application.py (status CHECK constraint).

/**
 * Valid values for `JobApplicationResponse.status`.
 * @typedef {"created" | "analysis_pending" | "analyzing" | "analysis_failed" |
 *   "ready_for_review" | "hold" | "advanced" | "rejected" | "archived"}
 *   JobApplicationStatusValue
 */

/** DB-backed status vocabulary; do not invent additional statuses. */
export const JobApplicationStatus = Object.freeze({
  CREATED: "created",
  ANALYSIS_PENDING: "analysis_pending",
  ANALYZING: "analyzing",
  ANALYSIS_FAILED: "analysis_failed",
  READY_FOR_REVIEW: "ready_for_review",
  HOLD: "hold",
  ADVANCED: "advanced",
  REJECTED: "rejected",
  ARCHIVED: "archived",
});

/**
 * Request body for `POST /api/v1/job-applications`.
 * @typedef {object} JobApplicationCreate
 * @property {import("./common.js").UUID} job_id
 * @property {import("./common.js").UUID} candidate_id
 * @property {import("./common.js").UUID} resume_id
 */

/**
 * Response for application create/get and `GET /api/v1/jobs/{job_id}/applications`.
 * @typedef {object} JobApplicationResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} organization_id
 * @property {import("./common.js").UUID} job_id
 * @property {import("./common.js").UUID} candidate_id
 * @property {import("./common.js").UUID} resume_id
 * @property {JobApplicationStatusValue} status
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * One compact, backend-classified evidence item inside an application summary.
 * The backend already decided `evidence_type` and the display `text`; the
 * frontend only re-buckets these into matched/partial/missing chip groups.
 * @typedef {object} RequirementEvidenceSummary
 * @property {string} [requirement_key]
 * @property {"matched" | "partial" | "missing"} evidence_type
 * @property {string} [text]
 */

/**
 * Response row for `GET /api/v1/job-applications` (org-wide aggregation).
 * `score` follows the stringified-score convention; `group` is the
 * backend-assigned score band (must_review / consider / lower_priority);
 * `evidence` summarizes the requirement-level match evidence of the current
 * evaluation so ranked list views can show real chips without per-row calls.
 * @typedef {object} ApplicationSummaryResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} candidate_id
 * @property {string} candidate_name
 * @property {import("./common.js").UUID} job_id
 * @property {string} job_title
 * @property {string} [score]
 * @property {string} [group]
 * @property {JobApplicationStatusValue} status
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {RequirementEvidenceSummary[]} [evidence]
 */

/**
 * JobApplication-supported API operations in the current backend.
 * @type {readonly ["create", "get", "listByJob"]}
 */
export const JOB_APPLICATION_OPERATIONS = Object.freeze([
  "create",
  "get",
  "listByJob",
]);
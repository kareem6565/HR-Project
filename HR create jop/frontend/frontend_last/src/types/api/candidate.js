// Candidate + CandidateProfile + job-scoped candidate pool contract.
// Source of truth:
//   backend/app/api/v1/schemas/candidates.py
//   backend/app/api/v1/schemas/candidate_profiles.py
//   backend/app/api/v1/schemas/candidate_pool.py
//   backend/app/services/candidate_pool_service.py (grouping bands)

/**
 * Valid values for `CandidateResponse.status`.
 * @typedef {"active" | "archived"} CandidateStatusValue
 */

/** DB-backed status vocabulary. */
export const CandidateStatus = Object.freeze({
  ACTIVE: "active",
  ARCHIVED: "archived",
});

/**
 * Request body for `POST /api/v1/candidates`.
 * @typedef {object} CandidateCreate
 * @property {string} full_name
 * @property {string} [email]
 * @property {string} [phone]
 */

/**
 * Response for candidate create/get.
 * @typedef {object} CandidateResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} organization_id
 * @property {string} full_name
 * @property {string} [email]
 * @property {string} [phone]
 * @property {CandidateStatusValue} status
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * Valid values for `CandidateProfileResponse.status`.
 * @typedef {"extracted" | "current" | "superseded" | "failed"} CandidateProfileStatusValue
 */

/** DB-backed candidate-profile status vocabulary. */
export const CandidateProfileStatus = Object.freeze({
  EXTRACTED: "extracted",
  CURRENT: "current",
  SUPERSEDED: "superseded",
  FAILED: "failed",
});

/**
 * Valid values for `CandidateProfileResponse.source`.
 * @typedef {"ai_extracted" | "hr_corrected" | "system_extracted"} CandidateProfileSourceValue
 */

/** DB-backed candidate-profile source vocabulary. */
export const CandidateProfileSource = Object.freeze({
  AI_EXTRACTED: "ai_extracted",
  HR_CORRECTED: "hr_corrected",
  SYSTEM_EXTRACTED: "system_extracted",
});

/**
 * Request body for `POST /api/v1/resumes/{resume_id}/profiles`.
 * @typedef {object} CandidateProfileCreate
 * @property {CandidateProfileStatusValue} status
 * @property {CandidateProfileSourceValue} source
 * @property {import("./common.js").JsonObject} profile_data
 */

/**
 * Response for candidate-profile create/list/get.
 * @typedef {object} CandidateProfileResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} resume_id
 * @property {number} version_number
 * @property {CandidateProfileStatusValue} status
 * @property {CandidateProfileSourceValue} source
 * @property {import("./common.js").JsonObject} profile_data
 * @property {import("./common.js").JsonObject} [provenance]
 * @property {boolean} is_current
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * Deterministic grouping bands for `JobCandidateSummary.group`
 * (backend candidate_pool_service; thresholds are fixed, not configurable):
 *   must_review     score >= 70
 *   consider        score >= 40 and < 70
 *   lower_priority  score < 40, OR no current evaluation (score = null)
 * @typedef {"must_review" | "consider" | "lower_priority"} CandidatePoolGroupValue
 */

export const CandidatePoolGroup = Object.freeze({
  MUST_REVIEW: "must_review",
  CONSIDER: "consider",
  LOWER_PRIORITY: "lower_priority",
});

/**
 * Read model returned by `GET /api/v1/jobs/{job_id}/candidates` (the
 * job-scoped candidate pool). It is a composition of the application,
 * candidate, current evaluation and latest decision. `status` is the
 * JobApplication status; `group` is the backend-assigned score band.
 *
 * AMBIGUITY NOTE: `score` is returned as a STRING (e.g. "85.000") to match
 * the evaluation response convention. Do NOT convert server-provided scores
 * into numbers for grouping or comparison — grouping is assigned by the
 * backend, never computed client-side.
 *
 * @typedef {object} JobCandidateSummary
 * @property {import("./common.js").UUID} candidate_id
 * @property {import("./common.js").UUID} application_id
 * @property {string} full_name
 * @property {string} [email]
 * @property {string} [phone]
 * @property {import("./application.js").JobApplicationStatusValue} status
 * @property {string} [score]
 * @property {CandidatePoolGroupValue} group
 * @property {import("./decision.js").HRDecisionValue} [decision]
 * @property {import("./common.js").ISO8601DateTime} [decision_created_at]
 */

/**
 * Query parameters for `GET /api/v1/jobs/{job_id}/candidates`.
 * `min_score`/`max_score` are numeric (0-100) in the query string, unlike the
 * stringified `score` in responses.
 * @typedef {object} CandidatePoolQuery
 * @property {import("./application.js").JobApplicationStatusValue} [status]
 * @property {import("./decision.js").HRDecisionValue} [decision]
 * @property {number} [min_score]
 * @property {number} [max_score]
 * @property {string} [search]  Case-insensitive match on full_name or email.
 * @property {CandidatePoolGroupValue} [group]
 */

/**
 * Response for the org-wide candidate roster `GET /api/v1/candidates`.
 * Unlike `CandidateResponse`, this deliberately omits `organization_id`,
 * `updated_at` and is the list-optimized shape the Candidates/Evaluations
 * pages are backed by.
 * @typedef {object} CandidateListResponse
 * @property {import("./common.js").UUID} id
 * @property {string} full_name
 * @property {string} [email]
 * @property {string} [phone]
 * @property {CandidateStatusValue} status
 * @property {import("./common.js").ISO8601DateTime} created_at
 */

/**
 * Query parameters for `GET /api/v1/candidates`.
 * @typedef {object} CandidateListQuery
 * @property {string} [search]  Case-insensitive match on full_name or email.
 * @property {CandidateStatusValue} [status]
 */

/**
 * Request body for `PATCH /api/v1/candidates/{candidate_id}`.
 * Only `email` and `phone` are editable today; `full_name` and `status`
 * are managed by the screening/archiving workflows.
 * @typedef {object} CandidateUpdate
 * @property {string} [email]
 * @property {string} [phone]
 */

/**
 * The backend supports an org-wide candidate list (`GET /candidates`) in
 * addition to single-candidate reads, contact updates (`PATCH /candidates/{id}`)
 * and the job-scoped pool (`GET /jobs/{id}/candidates`).
 * @type {readonly ["create", "get", "list", "update"]}
 */
export const CANDIDATE_OPERATIONS = Object.freeze(["create", "get", "list", "update"]);
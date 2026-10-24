// JobProfile API contract.
// Source of truth: backend/app/api/v1/schemas/job_profiles.py and
// backend/app/models/job_profile.py (status + source CHECK constraints).

/**
 * Valid values for `JobProfileResponse.status`.
 * @typedef {"draft" | "approved" | "superseded"} JobProfileStatusValue
 */

/** DB-backed status vocabulary. */
export const JobProfileStatus = Object.freeze({
  DRAFT: "draft",
  APPROVED: "approved",
  SUPERSEDED: "superseded",
});

/**
 * Valid values for `JobProfileResponse.source`.
 * @typedef {"ai_extracted" | "hr_edited" | "hr_created"} JobProfileSourceValue
 */

/** DB-backed source vocabulary. */
export const JobProfileSource = Object.freeze({
  AI_EXTRACTED: "ai_extracted",
  HR_EDITED: "hr_edited",
  HR_CREATED: "hr_created",
});

/**
 * Request body for `POST /api/v1/jobs/{job_id}/profiles`.
 * @typedef {object} JobProfileCreate
 * @property {JobProfileStatusValue} status
 * @property {JobProfileSourceValue} source
 * @property {import("./common.js").JsonObject} profile_data
 * @property {import("./common.js").JsonObject} [raw_input_snapshot]
 */

/**
 * Response for profile create/list/get and `POST /api/v1/job-profiles/{profile_id}/approve`.
 * @typedef {object} JobProfileResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} job_id
 * @property {number} version_number
 * @property {JobProfileStatusValue} status
 * @property {JobProfileSourceValue} source
 * @property {import("./common.js").JsonObject} profile_data
 * @property {import("./common.js").JsonObject} [raw_input_snapshot]
 * @property {import("./common.js").JsonObject} [provenance]
 * @property {boolean} is_current
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * JobProfile-supported API operations in the current backend.
 * @type {readonly ["create", "list", "get", "approve"]}
 */
export const JOB_PROFILE_OPERATIONS = Object.freeze([
  "create",
  "list",
  "get",
  "approve",
]);
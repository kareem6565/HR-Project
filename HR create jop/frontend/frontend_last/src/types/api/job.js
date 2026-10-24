// Job + JobRequirement API contract.
// Source of truth: backend/app/api/v1/schemas/jobs.py and
// backend/app/models/job.py (status CHECK constraint).

/**
 * Valid values for `JobResponse.status`.
 * @typedef {"draft" | "awaiting_profile_review" | "active" | "closed" | "archived"}
 *   JobStatusValue
 */

/** DB-backed status vocabulary; do not invent additional statuses. */
export const JobStatus = Object.freeze({
  DRAFT: "draft",
  AWAITING_PROFILE_REVIEW: "awaiting_profile_review",
  ACTIVE: "active",
  CLOSED: "closed",
  ARCHIVED: "archived",
});

/**
 * Request body for `POST /api/v1/jobs`.
 * @typedef {object} JobCreate
 * @property {string} title
 * @property {string} [raw_description]
 * @property {JobStatusValue} [status="draft"]
 * @property {string} [department]
 * @property {string} [location]
 * @property {string} [job_type]
 * @property {string} [experience]
 * @property {string[]} [requirements]
 * @property {string[]} [required_skills]
 */

/**
 * Request body for `PATCH /api/v1/jobs/{job_id}`. All fields optional;
 * only provided keys are updated.
 * @typedef {object} JobUpdate
 * @property {string} [title]
 * @property {string} [raw_description]
 * @property {JobStatusValue} [status]
 * @property {string} [department]
 * @property {string} [location]
 * @property {string} [job_type]
 * @property {string} [experience]
 * @property {string[]} [requirements]
 * @property {string[]} [required_skills]
 */

/**
 * Response for job create/list/get/update.
 * @typedef {object} JobResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} organization_id
 * @property {import("./common.js").UUID} [created_by_user_id]  Nullable in backend.
 * @property {string} title
 * @property {string} [raw_description]
 * @property {JobStatusValue} status
 * @property {string} [department]
 * @property {string} [location]
 * @property {string} [job_type]
 * @property {string} [experience]
 * @property {string[]} [requirements]
 * @property {string[]} [required_skills]
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * A single job requirement.
 *
 * AMBIGUITY NOTE: the backend has NO standalone JobRequirement resource or
 * endpoint. Requirements are stored as a JSON array of strings embedded in
 * the `requirements` property of Job (JSONB column) and are only returned as
 * part of Job responses. This typedef is provided purely so later phases can
 * reference the item shape explicitly.
 * @typedef {string} JobRequirement
 */

/**
 * Job-supported API operations in the current backend.
 * @type {readonly ["create", "list", "get", "update", "delete"]}
 */
export const JOB_OPERATIONS = Object.freeze([
  "create",
  "list",
  "get",
  "update",
  "delete",
]);

/**
 * Requirements-list shape as carried on Job payloads.
 * @typedef {string[]} JobRequirementList
 */
// Resume API contract.
// Source of truth: backend/app/api/v1/schemas/resumes.py and
// backend/app/models/resume.py (status CHECK constraint).

/**
 * Valid values for `ResumeResponse.status`.
 * @typedef {"uploaded" | "text_extracted" | "profile_extracted" | "archived"}
 *   ResumeStatusValue
 */

/** DB-backed status vocabulary. */
export const ResumeStatus = Object.freeze({
  UPLOADED: "uploaded",
  TEXT_EXTRACTED: "text_extracted",
  PROFILE_EXTRACTED: "profile_extracted",
  ARCHIVED: "archived",
});

/**
 * Request body for `POST /api/v1/candidates/{candidate_id}/resumes`
 * (JSON, references an already-stored file URI).
 * @typedef {object} ResumeCreate
 * @property {string} file_uri
 * @property {string} [original_filename]
 * @property {string} [content_type]
 * @property {number} [file_size_bytes]
 */

/**
 * Response for resume create/get/upload.
 * @typedef {object} ResumeResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} candidate_id
 * @property {string} file_uri
 * @property {string} [original_filename]
 * @property {string} [content_type]
 * @property {number} [file_size_bytes]
 * @property {ResumeStatusValue} status
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * `POST /api/v1/candidates/{candidate_id}/resumes/upload` is multipart
 * (field `file` of type File), NOT JSON; it returns the same ResumeResponse.
 */

/**
 * Resume-supported API operations in the current backend.
 * @type {readonly ["create", "upload", "get"]}
 */
export const RESUME_OPERATIONS = Object.freeze(["create", "upload", "get"]);
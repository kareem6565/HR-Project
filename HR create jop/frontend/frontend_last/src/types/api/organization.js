// Organization API contract.
// Source of truth: backend/app/api/v1/schemas/organizations.py and
// backend/app/models/organization.py (status CHECK constraint).

/**
 * Valid values for `OrganizationResponse.status`.
 * @typedef {"active" | "archived"} OrganizationStatusValue
 */

/** DB-backed status vocabulary; do not invent additional statuses. */
export const OrganizationStatus = Object.freeze({
  ACTIVE: "active",
  ARCHIVED: "archived",
});

/**
 * Request body for `POST /api/v1/organizations` (bootstrap/development only,
 * does not require identity headers).
 * @typedef {object} OrganizationCreate
 * @property {string} name
 */

/**
 * Response for `POST /api/v1/organizations`.
 * @typedef {object} OrganizationResponse
 * @property {import("./common.js").UUID} id
 * @property {string} name
 * @property {OrganizationStatusValue} status
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * There is no organization GET/update/list/delete endpoint in the current
 * backend. Only the bootstrap create is exposed.
 * @type {readonly ["create"]}
 */
export const ORGANIZATION_OPERATIONS = Object.freeze(["create"]);
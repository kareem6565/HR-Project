// User API contract.
// Source of truth: backend/app/api/v1/schemas/users.py and
// backend/app/models/user.py (status CHECK constraint).

/**
 * Valid values for `UserResponse.status`.
 * @typedef {"active" | "inactive"} UserStatusValue
 */

/** DB-backed status vocabulary; do not invent additional statuses. */
export const UserStatus = Object.freeze({
  ACTIVE: "active",
  INACTIVE: "inactive",
});

/**
 * Request body for `POST /api/v1/organizations/{org_id}/users`
 * (bootstrap/development only, does not require identity headers).
 * @typedef {object} UserCreate
 * @property {string} email
 * @property {string} full_name
 */

/**
 * Response for `POST /api/v1/organizations/{org_id}/users`.
 * @typedef {object} UserResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} organization_id
 * @property {string} email
 * @property {string} full_name
 * @property {UserStatusValue} status
 * @property {import("./common.js").ISO8601DateTime} created_at
 * @property {import("./common.js").ISO8601DateTime} updated_at
 */

/**
 * There is no user GET/update/list/delete endpoint in the current backend.
 * Only the bootstrap create is exposed.
 * @type {readonly ["create"]}
 */
export const USER_OPERATIONS = Object.freeze(["create"]);
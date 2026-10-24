// Shared scalars and conventions for the HERA backend API contract layer.
//
// SOURCE OF TRUTH: the FastAPI backend schemas in backend/app/api/v1/schemas
// and the PostgreSQL CHECK constraints on statuses. Frontend UI models
// (camelCase display shapes) are NOT part of this contract layer — services
// adapt them separately. Field names here deliberately match the backend
// exactly (snake_case), including identifiers like `job_id`.
//
// Identity: the MVP backend has NO authentication. It resolves the caller
// from two development-only headers (see backend/app/api/v1/deps.py):
//   X-Organization-Id, X-User-Id.

/** @typedef {string} UUID A 36-char lowercase UUID string (validated by the backend). */
/** @typedef {string} ISO8601DateTime Backend timestamp serialized as an ISO-8601 string. */

/**
 * An arbitrary JSON object (backend `dict[str, Any]` stored as JSONB).
 * The internal shape of these payloads is owned by the backend AI/workflow
 * layer and is intentionally opaque to the frontend contract.
 * @typedef {Object<string, *>} JsonObject
 */

// Development identity header names used by every org-scoped endpoint.
// These mirror backend/app/api/v1/deps.py `get_request_context`.
export const IDENTITY_HEADERS = Object.freeze({
  USER: "X-User-Id",
  ORGANIZATION: "X-Organization-Id",
});

/**
 * Base API prefix for all backend routes. Do not hardcode hostnames; use
 * VITE_API_BASE_URL (from the Phase B apiClient) instead.
 * @type {string}
 */
export const API_PREFIX = "/api/v1";

/**
 * FastAPI error response envelope.
 * - HTTPException -> `{ "detail": "<message>" }`
 * - RequestValidationError (422) -> `{ "detail": [ { loc, msg, type, ... } ] }`
 * @typedef {object} ApiErrorResponse
 * @property {string | Array<object>} detail
 */

/**
 * `GET /api/v1/health` returns a bare object, NOT an envelope.
 * @typedef {object} HealthResponse
 * @property {"ok"} status
 */
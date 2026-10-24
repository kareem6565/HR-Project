// AI-settings contract.
// Source of truth: backend/app/api/v1/schemas/ai_settings.py.
// Security: the API never returns the API key itself — only whether one is
// set and where it came from.

/**
 * Where the active Soal API key originates.
 * @typedef {"runtime" | "environment" | "none"} ApiKeySourceValue
 */

export const ApiKeySource = Object.freeze({
  RUNTIME: "runtime",
  ENVIRONMENT: "environment",
  NONE: "none",
});

/**
 * The active AI provider resolution.
 * @typedef {"soal" | "fake"} AiProviderValue
 */

export const AiProvider = Object.freeze({
  SOAL: "soal",
  FAKE: "fake",
});

/**
 * Response for `GET /api/v1/settings/ai`.
 * `has_api_key` reports presence only — the key value is never returned.
 * @typedef {object} AISettingsResponse
 * @property {AiProviderValue} provider
 * @property {string} model  Active Soal model (empty when provider is fake).
 * @property {ApiKeySourceValue} api_key_source
 * @property {boolean} has_api_key
 */

/**
 * Request body for `POST /api/v1/settings/ai/api-key`.
 * @typedef {object} SetApiKeyRequest
 * @property {string} api_key
 */

/**
 * Request body for `POST /api/v1/settings/ai/verify`. The key is optional —
 * when omitted the backend verifies the currently active key.
 * @typedef {object} VerifyApiKeyRequest
 * @property {string} [api_key]
 */

/**
 * Response for `POST /api/v1/settings/ai/verify`.
 * The endpoint returns `ok: false` with a human-readable `message` rather than
 * an HTTP error, so the Settings page can render verification inline.
 * @typedef {object} VerifyApiKeyResponse
 * @property {boolean} ok
 * @property {string} message
 * @property {string} model
 */

/**
 * AI-settings operations in the current backend.
 * @type {readonly ["get", "setApiKey", "clearApiKey", "verify"]}
 */
export const AI_SETTINGS_OPERATIONS = Object.freeze(["get", "setApiKey", "clearApiKey", "verify"]);

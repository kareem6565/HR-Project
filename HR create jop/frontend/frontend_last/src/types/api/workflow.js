// WorkflowRun + AITrace + workflow-run response contract.
// Source of truth: backend/app/api/v1/schemas/workflows.py,
// backend/app/models/workflow_run.py and backend/app/models/ai_trace.py.

/**
 * Valid values for `WorkflowRunResponse.workflow_type`.
 * Observed values from backend/app/ai/workflows/*; there is no DB CHECK
 * constraint on workflow_type, so treat these as the current vocabulary,
 * not an exhaustive enum.
 * @typedef {"job_profile_extraction" | "candidate_profile_extraction" |
 *   "candidate_evaluation"} WorkflowTypeValue
 */

export const WorkflowType = Object.freeze({
  JOB_PROFILE_EXTRACTION: "job_profile_extraction",
  CANDIDATE_PROFILE_EXTRACTION: "candidate_profile_extraction",
  CANDIDATE_EVALUATION: "candidate_evaluation",
});

/**
 * Valid values for `WorkflowRunResponse.status`.
 * @typedef {"pending" | "running" | "waiting_for_human" | "completed" |
 *   "failed" | "cancelled"} WorkflowRunStatusValue
 */

/** DB-backed workflow-run status vocabulary. */
export const WorkflowRunStatus = Object.freeze({
  PENDING: "pending",
  RUNNING: "running",
  WAITING_FOR_HUMAN: "waiting_for_human",
  COMPLETED: "completed",
  FAILED: "failed",
  CANCELLED: "cancelled",
});

/**
 * Valid values for `WorkflowRunResponse.related_entity_type`.
 * @typedef {"job" | "candidate" | "resume" | "job_application" | "job_profile" |
 *   "candidate_profile" | "candidate_evaluation"} WorkflowRelatedEntityTypeValue
 */

/** DB-backed related-entity vocabulary (NULL when unrelated to an entity). */
export const WorkflowRelatedEntityType = Object.freeze({
  JOB: "job",
  CANDIDATE: "candidate",
  RESUME: "resume",
  JOB_APPLICATION: "job_application",
  JOB_PROFILE: "job_profile",
  CANDIDATE_PROFILE: "candidate_profile",
  CANDIDATE_EVALUATION: "candidate_evaluation",
});

/**
 * Response for `GET /api/v1/workflow-runs/{run_id}`.
 * @typedef {object} WorkflowRunResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} organization_id
 * @property {WorkflowTypeValue} workflow_type
 * @property {WorkflowRunStatusValue} status
 * @property {WorkflowRelatedEntityTypeValue} [related_entity_type]
 * @property {import("./common.js").UUID} [related_entity_id]
 * @property {import("./common.js").ISO8601DateTime} [started_at]
 * @property {import("./common.js").ISO8601DateTime} [completed_at]
 * @property {import("./common.js").ISO8601DateTime} created_at
 */

/**
 * Valid values for `AITraceResponse.status`.
 * @typedef {"started" | "succeeded" | "failed" | "validation_failed" | "retried"}
 *   AITraceStatusValue
 */

/** DB-backed AI-trace status vocabulary. */
export const AITraceStatus = Object.freeze({
  STARTED: "started",
  SUCCEEDED: "succeeded",
  FAILED: "failed",
  VALIDATION_FAILED: "validation_failed",
  RETRIED: "retried",
});

/**
 * Response for `GET /api/v1/ai-traces/{trace_id}`.
 *
 * Privacy rule: `input_reference`/`output_reference` must never be rendered
 * as raw AI prompts or outputs in the UI. `token_usage` is opaque.
 *
 * @typedef {object} AITraceResponse
 * @property {import("./common.js").UUID} id
 * @property {import("./common.js").UUID} workflow_step_trace_id
 * @property {string} ai_component_name
 * @property {string} [provider]
 * @property {string} [model_name]
 * @property {string} [prompt_version]
 * @property {AITraceStatusValue} status
 * @property {number} [latency_ms]
 * @property {import("./common.js").JsonObject} [token_usage]
 * @property {import("./common.js").JsonObject} [input_reference]
 * @property {import("./common.js").JsonObject} [output_reference]
 * @property {import("./common.js").JsonObject} [validation_error]
 * @property {import("./common.js").ISO8601DateTime} created_at
 */

/**
 * Request body for `POST /api/v1/resumes/{resume_id}/extract-profile`.
 * When omitted, the backend uses the resume's stored extracted text.
 * @typedef {object} CandidateProfileExtractionRequest
 * @property {string} [resume_text]
 */

/**
 * Result of `POST /api/v1/jobs/{job_id}/extract-profile`.
 * @typedef {object} JobProfileExtractionResponse
 * @property {import("./common.js").UUID} profile_id
 * @property {import("./common.js").UUID} workflow_run_id
 * @property {number} version_number
 */

/**
 * Result of `POST /api/v1/resumes/{resume_id}/extract-profile`.
 * @typedef {object} CandidateProfileExtractionResponse
 * @property {import("./common.js").UUID} profile_id
 * @property {import("./common.js").UUID} workflow_run_id
 * @property {number} version_number
 */

/**
 * Result of `POST /api/v1/job-applications/{application_id}/evaluate`.
 * @typedef {object} CandidateEvaluationRunResponse
 * @property {import("./common.js").UUID} evaluation_id
 * @property {import("./common.js").UUID} workflow_run_id
 * @property {number} version_number
 */

/**
 * One screened candidate inside `JobScreeningResponse.screened`.
 * `score` follows the stringified-score convention.
 * @typedef {object} ScreenedCandidateResponse
 * @property {import("./common.js").UUID} candidate_id
 * @property {import("./common.js").UUID} resume_id
 * @property {import("./common.js").UUID} application_id
 * @property {import("./common.js").UUID} evaluation_id
 * @property {string} [score]
 */

/**
 * Result of `POST /api/v1/jobs/{job_id}/screen` (multipart `files`).
 * @typedef {object} JobScreeningResponse
 * @property {import("./common.js").UUID} job_id
 * @property {string} job_title
 * @property {ScreenedCandidateResponse[]} screened
 */

/**
 * Observability / workflow operations in the current backend.
 * @type {readonly ["getWorkflowRun", "getAITrace"]}
 */
export const OBSERVABILITY_OPERATIONS = Object.freeze(["getWorkflowRun", "getAITrace"]);
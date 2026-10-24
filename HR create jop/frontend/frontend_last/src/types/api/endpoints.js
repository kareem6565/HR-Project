// Complete endpoint catalog for the current backend API.
//
// Source of truth: the route decorators across backend/app/api/v1/routes/*.py
// (verified against the running server's OpenAPI). Base path is /api/v1
// (API_PREFIX in common.js). Every entry lists the HTTP method, the path
// template, the request/response contract refs, and the success status where
// it differs from the default 200.
//
// Note: the backend has no response envelope and no pagination — Lists are
// returned as bare JSON arrays, entities as bare objects.

import { API_PREFIX } from "./common.js";

/**
 * Substitute `{name}` placeholders in a path template with `params` values.
 * @param {string} pathTemplate e.g. `${API_PREFIX}/jobs/{job_id}/candidates`
 * @param {Record<string, string>} [params]
 * @returns {string}
 */
export function apiPath(pathTemplate, params = {}) {
  return pathTemplate.replace(/\{(\w+)\}/g, (_, name) => {
    const value = params[name];
    if (value === undefined || value === null || value === "") {
      throw new Error(`apiPath: missing parameter '${name}' for path '${pathTemplate}'`);
    }
    return encodeURIComponent(String(value));
  });
}

/**
 * One backend endpoint.
 * @typedef {object} EndpointDefinition
 * @property {string} name
 * @property {"GET" | "POST" | "PATCH" | "DELETE"} method
 * @property {string} path  Template with `{param}` placeholders.
 * @property {string} [request]  JSDoc typedef ref of the JSON request body.
 * @property {string} [response]  JSDoc typedef ref of the response body.
 * @property {number} [successStatus]  Overrides 200 when the backend returns 201/204.
 * @property {string} [multipart]  Field name(s) when the request is multipart.
 * @property {string} [note]
 */

/** @type {readonly EndpointDefinition[]} */
export const API_ENDPOINTS = Object.freeze([
  // ---- bootstrap / system ----
  { name: "auth.health", method: "GET", path: `${API_PREFIX}/health`, response: "HealthResponse" },
  {
    name: "organization.create",
    method: "POST",
    path: `${API_PREFIX}/organizations`,
    request: "OrganizationCreate",
    response: "OrganizationResponse",
    successStatus: 201,
    note: "Development bootstrap only; no identity headers required.",
  },
  {
    name: "user.create",
    method: "POST",
    path: `${API_PREFIX}/organizations/{org_id}/users`,
    request: "UserCreate",
    response: "UserResponse",
    successStatus: 201,
    note: "Development bootstrap only; no identity headers required.",
  },

  // ---- jobs ----
  { name: "jobs.create", method: "POST", path: `${API_PREFIX}/jobs`, request: "JobCreate", response: "JobResponse", successStatus: 201 },
  { name: "jobs.list", method: "GET", path: `${API_PREFIX}/jobs`, response: "JobResponse[]" },
  { name: "jobs.delete", method: "DELETE", path: `${API_PREFIX}/jobs/{job_id}`, successStatus: 204, note: "409 if the job has applications/profiles." },
  { name: "jobs.get", method: "GET", path: `${API_PREFIX}/jobs/{job_id}`, response: "JobResponse" },
  { name: "jobs.update", method: "PATCH", path: `${API_PREFIX}/jobs/{job_id}`, request: "JobUpdate", response: "JobResponse" },
  {
    name: "jobs.listApplications",
    method: "GET",
    path: `${API_PREFIX}/jobs/{job_id}/applications`,
    response: "JobApplicationResponse[]",
  },
  {
    name: "jobs.listProfiles",
    method: "GET",
    path: `${API_PREFIX}/jobs/{job_id}/profiles`,
    response: "JobProfileResponse[]",
  },
  {
    name: "jobs.createProfile",
    method: "POST",
    path: `${API_PREFIX}/jobs/{job_id}/profiles`,
    request: "JobProfileCreate",
    response: "JobProfileResponse",
    successStatus: 201,
  },
  {
    name: "jobProfile.extendFromJob",
    method: "POST",
    path: `${API_PREFIX}/jobs/{job_id}/extract-profile`,
    response: "JobProfileExtractionResponse",
    successStatus: 201,
    note: "Runs the AI job-profile extraction workflow (FakeAIProvider in MVP).",
  },
  {
    name: "jobs.listCandidates",
    method: "GET",
    path: `${API_PREFIX}/jobs/{job_id}/candidates`,
    response: "JobCandidateSummary[]",
    note: "Query params = CandidatePoolQuery (status, decision, min_score, max_score, search, group).",
  },
  {
    name: "jobs.screenCandidates",
    method: "POST",
    path: `${API_PREFIX}/jobs/{job_id}/screen`,
    response: "JobScreeningResponse",
    successStatus: 201,
    multipart: "files",
    note: "Batch candidate+resume+profile+application+evaluation run.",
  },

  // ---- job profiles ----
  {
    name: "jobProfile.get",
    method: "GET",
    path: `${API_PREFIX}/job-profiles/{profile_id}`,
    response: "JobProfileResponse",
  },
  {
    name: "jobProfile.approve",
    method: "POST",
    path: `${API_PREFIX}/job-profiles/{profile_id}/approve`,
    response: "JobProfileResponse",
  },

  // ---- candidates ----
  { name: "candidates.create", method: "POST", path: `${API_PREFIX}/candidates`, request: "CandidateCreate", response: "CandidateResponse", successStatus: 201 },
  { name: "candidates.get", method: "GET", path: `${API_PREFIX}/candidates/{candidate_id}`, response: "CandidateResponse" },
  {
    name: "resumes.create",
    method: "POST",
    path: `${API_PREFIX}/candidates/{candidate_id}/resumes`,
    request: "ResumeCreate",
    response: "ResumeResponse",
    successStatus: 201,
  },
  {
    name: "resumes.upload",
    method: "POST",
    path: `${API_PREFIX}/candidates/{candidate_id}/resumes/upload`,
    response: "ResumeResponse",
    successStatus: 201,
    multipart: "file",
  },

  // ---- resumes ----
  { name: "resumes.get", method: "GET", path: `${API_PREFIX}/resumes/{resume_id}`, response: "ResumeResponse" },
  {
    name: "candidateProfile.create",
    method: "POST",
    path: `${API_PREFIX}/resumes/{resume_id}/profiles`,
    request: "CandidateProfileCreate",
    response: "CandidateProfileResponse",
    successStatus: 201,
  },
  {
    name: "candidateProfile.list",
    method: "GET",
    path: `${API_PREFIX}/resumes/{resume_id}/profiles`,
    response: "CandidateProfileResponse[]",
  },
  {
    name: "candidateProfile.extendFromResume",
    method: "POST",
    path: `${API_PREFIX}/resumes/{resume_id}/extract-profile`,
    request: "CandidateProfileExtractionRequest",
    response: "CandidateProfileExtractionResponse",
    successStatus: 201,
  },

  // ---- candidate profiles ----
  {
    name: "candidateProfile.get",
    method: "GET",
    path: `${API_PREFIX}/candidate-profiles/{profile_id}`,
    response: "CandidateProfileResponse",
  },

  // ---- job applications ----
  {
    name: "jobApplications.list",
    method: "GET",
    path: `${API_PREFIX}/job-applications`,
    response: "ApplicationSummaryResponse[]",
    note: "Org-wide application summaries with candidate name, job title, score, backend-assigned group, and per-requirement evidence summary. Query param: status.",
  },
  {
    name: "jobApplications.create",
    method: "POST",
    path: `${API_PREFIX}/job-applications`,
    request: "JobApplicationCreate",
    response: "JobApplicationResponse",
    successStatus: 201,
  },
  {
    name: "jobApplications.get",
    method: "GET",
    path: `${API_PREFIX}/job-applications/{application_id}`,
    response: "JobApplicationResponse",
  },
  {
    name: "jobApplications.reviewBundle",
    method: "GET",
    path: `${API_PREFIX}/job-applications/{application_id}/review-bundle`,
    response: "ReviewBundleResponse",
    note: "Single-call aggregation for the HR review screen: application, candidate, job, evaluations, evidence, pool row.",
  },
  {
    name: "jobApplications.triggerEvaluation",
    method: "POST",
    path: `${API_PREFIX}/job-applications/{application_id}/evaluations`,
    request: "CandidateEvaluationCreate",
    response: "CandidateEvaluationRunResponse",
    successStatus: 201,
    note: "Triggers a new AI evaluation run (FakeAIProvider).",
  },
  {
    name: "jobApplications.evaluate",
    method: "POST",
    path: `${API_PREFIX}/job-applications/{application_id}/evaluate`,
    response: "CandidateEvaluationRunResponse",
    successStatus: 201,
  },
  {
    name: "jobApplications.listEvaluations",
    method: "GET",
    path: `${API_PREFIX}/job-applications/{application_id}/evaluations`,
    response: "CandidateEvaluationResponse[]",
  },
  {
    name: "jobApplications.createDecision",
    method: "POST",
    path: `${API_PREFIX}/job-applications/{application_id}/decisions`,
    request: "HRDecisionCreate",
    response: "HRDecisionResponse",
    successStatus: 201,
  },

  // ---- candidate pool ----
  {
    name: "candidatePool.talentPool",
    method: "GET",
    path: `${API_PREFIX}/talent-pool`,
    response: "TalentPoolRowResponse[]",
    note: "Org-wide talent pool: all held + advanced candidates with job context.",
  },

  // ---- evaluations ----
  { name: "evaluations.get", method: "GET", path: `${API_PREFIX}/evaluations/{evaluation_id}`, response: "CandidateEvaluationResponse" },
  {
    name: "evaluations.listEvidence",
    method: "GET",
    path: `${API_PREFIX}/evaluations/{evaluation_id}/evidence`,
    response: "MatchEvidenceResponse[]",
  },

  // ---- observability ----
  {
    name: "observability.getWorkflowRun",
    method: "GET",
    path: `${API_PREFIX}/workflow-runs/{run_id}`,
    response: "WorkflowRunResponse",
  },
  {
    name: "observability.getAITrace",
    method: "GET",
    path: `${API_PREFIX}/ai-traces/{trace_id}`,
    response: "AITraceResponse",
  },

  // ---- AI settings ----
  {
    name: "aiSettings.get",
    method: "GET",
    path: `${API_PREFIX}/settings/ai`,
    response: "AISettingsResponse",
    note: "Reports provider, model, key source and presence — never the key itself.",
  },
  {
    name: "aiSettings.setApiKey",
    method: "POST",
    path: `${API_PREFIX}/settings/ai/api-key`,
    request: "SetApiKeyRequest",
    response: "AISettingsResponse",
    note: "Sets an in-memory runtime Soal key override (resets on restart).",
  },
  {
    name: "aiSettings.clearApiKey",
    method: "DELETE",
    path: `${API_PREFIX}/settings/ai/api-key`,
    response: "AISettingsResponse",
  },
  {
    name: "aiSettings.verify",
    method: "POST",
    path: `${API_PREFIX}/settings/ai/verify`,
    request: "VerifyApiKeyRequest",
    response: "VerifyApiKeyResponse",
    note: "Optional api_key body; verifies the active key when omitted.",
  },
]);
import apiClient from "./apiClient";

// Evaluation + match-evidence service.
// Endpoints: GET /evaluations/{id}, GET /evaluations/{id}/evidence,
// GET /job-applications/{id}/evaluations. Response contracts live in
// src/types/api/evaluation.js and src/types/api/matchEvidence.js.

export async function getEvaluationById(evaluationId) {
  const { data } = await apiClient.get(`/evaluations/${evaluationId}`);
  return data;
}

export async function getEvaluationEvidence(evaluationId) {
  const { data } = await apiClient.get(`/evaluations/${evaluationId}/evidence`);
  return Array.isArray(data) ? data : [];
}

export async function listEvaluationsByApplication(applicationId) {
  const { data } = await apiClient.get(`/job-applications/${applicationId}/evaluations`);
  return Array.isArray(data) ? data : [];
}

// Latest score for an application, normalized to a number for display.
// The backend returns scores as strings ("85.000"); the raw string is never
// used for grouping (the backend assigns `group` on the pool rows).
export async function latestEvaluationScore(applicationId) {
  try {
    const evals = await listEvaluationsByApplication(applicationId);
    const current = evals.find((e) => e.is_current) || evals[evals.length - 1];
    if (!current || current.score === undefined || current.score === null) return null;
    const score = Number(current.score);
    return Number.isFinite(score) ? Math.round(score) : null;
  } catch {
    return null;
  }
}
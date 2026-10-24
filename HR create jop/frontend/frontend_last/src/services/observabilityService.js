import apiClient from "./apiClient";

// Observability service for AI workflow runs and AI traces.
// Endpoints: GET /workflow-runs/{id}, GET /ai-traces/{id}. Contracts in
// src/types/api/workflow.js. Note: neither resource has a list endpoint, so
// lookups are always by id.

export async function getWorkflowRun(runId) {
  const { data } = await apiClient.get(`/workflow-runs/${runId}`);
  return data;
}

export async function getAITrace(traceId) {
  const { data } = await apiClient.get(`/ai-traces/${traceId}`);
  return data;
}
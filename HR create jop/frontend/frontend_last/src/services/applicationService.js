import apiClient from "./apiClient";

// Application service backed by the real backend.
//
// Uses the org-wide GET /job-applications aggregation endpoint (Phase 4)
// instead of composing data from multiple per-job calls. The backend's
// ReviewService.list_application_summaries returns everything the
// ApplicationsList page needs in a single request: candidate name, job
// title, latest score, status, and created_at.

export async function getApplications(status) {
  const params = {};
  if (status && status !== "all") params.status = status;
  const { data } = await apiClient.get("/job-applications", { params });
  const rows = Array.isArray(data) ? data : [];
  return rows.map((row) => ({
    id: row.id,
    candidateId: row.candidate_id,
    candidateName: row.candidate_name,
    job: row.job_title,
    appliedAt: row.created_at,
    score: row.score,
    group: row.group,
    status: row.status,
  }));
}

export async function getApplicationById(id) {
  const { data } = await apiClient.get(`/job-applications/${id}`);
  return data;
}

export async function createApplication(payload) {
  const { data } = await apiClient.post("/job-applications", payload);
  return data;
}

export async function evaluateApplication(applicationId) {
  const { data } = await apiClient.post(`/job-applications/${applicationId}/evaluate`);
  return data;
}

export async function createDecision(applicationId, payload) {
  const { data } = await apiClient.post(`/job-applications/${applicationId}/decisions`, payload);
  return data;
}

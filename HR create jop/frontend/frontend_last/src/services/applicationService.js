import apiClient from "./apiClient";

// Application service backed by the real backend.
//
// Uses the org-wide GET /job-applications aggregation endpoint (Phase 4)
// instead of composing data from multiple per-job calls. The backend's
// ReviewService.list_application_summaries returns everything the
// ApplicationsList page needs in a single request: candidate name, job
// title, latest score, status, and created_at.

export async function getApplications(filters = {}) {
  const options = typeof filters === "string" ? { status: filters } : filters;
  const params = {};
  Object.entries(options || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "" && value !== "all") {
      params[key] = value;
    }
  });
  const { data } = await apiClient.get("/job-applications", { params });
  const rows = Array.isArray(data) ? data : (data?.items || []);
  const items = rows.map((row) => ({
    id: row.id,
    candidateId: row.candidate_id,
    candidateName: row.candidate_name,
    email: row.candidate_email,
    phone: row.candidate_phone,
    job: row.job_title,
    jobId: row.job_id,
    appliedAt: row.created_at,
    source: row.source,
    sourceMedium: row.source_medium,
    sourceCampaign: row.source_campaign,
    score: row.score,
    group: row.group,
    status: row.status,
    screeningStatus: row.screening_status || "not_started",
    decisionStatus: row.decision_status || "pending_review",
    decisionCreatedAt: row.decision_created_at,
    evidence: Array.isArray(row.evidence) ? row.evidence : [],
  }));
  return Array.isArray(data) ? items : { items, page: data.page, pageSize: data.page_size, total: data.total, pages: data.pages };
}

export async function getApplicationJobs() {
  const { data } = await apiClient.get("/jobs");
  return (Array.isArray(data) ? data : []).map(({ id, title }) => ({ id, title }));
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

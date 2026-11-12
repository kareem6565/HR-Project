import apiClient from "./apiClient";

export async function listJobDistributions(jobId) {
  const { data } = await apiClient.get(`/jobs/${jobId}/distributions`);
  return Array.isArray(data) ? data : [];
}

export async function createJobDistribution(jobId, payload) {
  const { data } = await apiClient.post(`/jobs/${jobId}/distributions`, payload);
  return data;
}

export async function generateDistributionPost(distributionId) {
  const { data } = await apiClient.post(`/job-distributions/${distributionId}/generate`);
  return data;
}

export async function updateJobDistribution(distributionId, payload) {
  const { data } = await apiClient.patch(`/job-distributions/${distributionId}`, payload);
  return data;
}

export async function markJobDistributionShared(distributionId, externalPostUrl = "") {
  const { data } = await apiClient.post(`/job-distributions/${distributionId}/mark-shared`, {
    hr_reviewed: true,
    ...(externalPostUrl ? { external_post_url: externalPostUrl } : {}),
  });
  return data;
}

export async function getJobDistributionAnalytics(rangeDays = 30) {
  const { data } = await apiClient.get("/distribution-analytics", {
    params: { range_days: rangeDays },
  });
  return data;
}

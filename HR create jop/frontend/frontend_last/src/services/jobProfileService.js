import apiClient from "./apiClient";

// Job-profile service backed by the real backend.
// Endpoints: GET/POST /jobs/{id}/profiles, POST /jobs/{id}/extract-profile,
// GET /job-profiles/{id}, POST /job-profiles/{id}/approve.

export async function listJobProfiles(jobId) {
  const { data } = await apiClient.get(`/jobs/${jobId}/profiles`);
  return Array.isArray(data) ? data : [];
}

export async function getJobProfile(profileId) {
  const { data } = await apiClient.get(`/job-profiles/${profileId}`);
  return data;
}

export async function createJobProfile(jobId, payload) {
  const { data } = await apiClient.post(`/jobs/${jobId}/profiles`, payload);
  return data;
}

// Runs the AI job-profile extraction workflow; returns the created profile id
// plus its workflow run (JobProfileExtractionResponse).
export async function extractJobProfile(jobId) {
  const { data } = await apiClient.post(`/jobs/${jobId}/extract-profile`);
  return data;
}

export async function approveJobProfile(profileId) {
  const { data } = await apiClient.post(`/job-profiles/${profileId}/approve`);
  return data;
}
import axios from "axios";

// Minimal API client for the FastAPI backend.
//
// The backend uses header-based identity (X-User-Id / X-Organization-Id)
// with no login flow, so we read demo IDs from the environment and attach
// them to every request. No authentication or authorization changes are
// made on the backend side.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

const organizationId = import.meta.env.VITE_ORG_ID || "";
const userId = import.meta.env.VITE_USER_ID || "";

export const client = axios.create({
  baseURL: `${BASE_URL}${API_PREFIX}`,
  headers: {
    "Content-Type": "application/json",
    "X-Organization-Id": organizationId,
    "X-User-Id": userId,
  },
});

export const identity = {
  organizationId,
  userId,
  configured: Boolean(organizationId && userId),
};

export async function checkHealth() {
  // Health is public (no headers needed), but the client adds them anyway.
  const { data } = await client.get("/health");
  return data;
}

export async function createJob({ title, raw_description }) {
  const { data } = await client.post("/jobs", { title, raw_description });
  return data;
}

export async function getJob(jobId) {
  const { data } = await client.get(`/jobs/${jobId}`);
  return data;
}

export async function getJobCandidates(jobId, params = {}) {
  const { data } = await client.get(`/jobs/${jobId}/candidates`, { params });
  return data;
}

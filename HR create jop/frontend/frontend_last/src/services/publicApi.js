import axios from "axios";

const baseURL = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");

// Public career traffic intentionally uses a client with no HR auth interceptor.
const publicApi = axios.create({ baseURL, withCredentials: false });

export async function getPublicJob(publicId, params = {}) {
  const { data } = await publicApi.get(`/public/jobs/${encodeURIComponent(publicId)}`, { params });
  return data;
}

export async function getPublicApplicationConfig() {
  const { data } = await publicApi.get("/public/application-config");
  return data;
}

export async function submitPublicApplication(publicId, formData, idempotencyKey) {
  const { data } = await publicApi.post(
    `/public/jobs/${encodeURIComponent(publicId)}/applications`,
    formData,
    { headers: { "Idempotency-Key": idempotencyKey } },
  );
  return data;
}

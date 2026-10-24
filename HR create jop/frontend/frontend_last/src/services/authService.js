import apiClient from "./apiClient";
import { clearToken, setToken } from "./authStorage";

/**
 * Authentication service communicating with HERA backend endpoints.
 */

export async function login({ email, password, organizationId }) {
  const payload = {
    email: email.trim(),
    password,
  };
  if (organizationId) {
    payload.organization_id = organizationId;
  }

  const { data } = await apiClient.post("/auth/login", payload);
  if (data?.access_token) {
    setToken(data.access_token);
  }
  return data;
}

export async function exchangeHRSsoAssertion(assertion) {
  const { data } = await apiClient.post("/auth/sso/exchange", { assertion });
  if (data?.access_token) {
    setToken(data.access_token);
  }
  return data;
}

export async function getCurrentUser() {
  const { data } = await apiClient.get("/auth/me");
  return data;
}

export async function logout() {
  try {
    await apiClient.post("/auth/logout");
  } finally {
    clearToken();
  }
}

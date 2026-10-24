import axios from "axios";
import { clearToken, getToken } from "./authStorage";

// Central Axios instance for talking to the FastAPI backend.
// Every service file imports this instead of calling axios directly.

const defaultBaseURL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

const apiClient = axios.create({
  baseURL: defaultBaseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

let unauthorizedHandler = null;

/**
 * Register a callback invoked when an authenticated request receives 401 Unauthorized.
 * Used by AuthContext to reset state and navigate to /login without loops.
 */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

/**
 * Determine if a request URL points to the trusted backend origin.
 * Prevents attaching Bearer access tokens to third-party or untrusted external URLs.
 */
export function isApprovedBackendRequest(config) {
  if (!config?.url) return false;
  // Relative paths are always within the trusted dev proxy / same origin
  if (config.url.startsWith("/") && !config.url.startsWith("//")) {
    return true;
  }
  try {
    const origin = typeof window !== "undefined" && window.location?.origin
      ? window.location.origin
      : "http://localhost:5173";
    const base = new URL(config.baseURL || defaultBaseURL, origin);
    const target = new URL(config.url, base);
    return target.origin === base.origin;
  } catch {
    return false;
  }
}

// Request Interceptor:
// 1. Attach Bearer token to approved backend requests.
// 2. Never attach legacy X-User-Id / X-Organization-Id headers.
// 3. Delete manual multipart/form-data Content-Type so browser sets correct boundary.
apiClient.interceptors.request.use((config) => {
  // Never send legacy headers
  if (config.headers) {
    delete config.headers["X-User-Id"];
    delete config.headers["X-Organization-Id"];
  }

  // Handle FormData: let browser generate multipart boundary
  if (config.data instanceof FormData && config.headers) {
    delete config.headers["Content-Type"];
  }

  // Attach Bearer token to approved backend origins only
  const token = getToken();
  if (token && isApprovedBackendRequest(config)) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// Response Interceptor:
// Handle 401 Unauthorized by clearing session and notifying auth handler
// (ignoring 401s from the login request itself to prevent loops).
// 403 Forbidden is preserved so callers can display access-denied state.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url || "";
    const isLoginRequest = url.includes("/auth/login");

    if (status === 401 && !isLoginRequest) {
      clearToken();
      if (typeof unauthorizedHandler === "function") {
        unauthorizedHandler(error);
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
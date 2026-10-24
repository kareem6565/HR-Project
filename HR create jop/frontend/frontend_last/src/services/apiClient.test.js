import { describe, it, expect, beforeEach, vi } from "vitest";
import apiClient, { isApprovedBackendRequest, setUnauthorizedHandler } from "./apiClient";
import * as authStorage from "./authStorage";

describe("apiClient security containment and authentication", () => {
  beforeEach(() => {
    authStorage.clearToken();
    vi.restoreAllMocks();
  });

  it("does not default to an unapproved third-party domain such as soal.help", () => {
    const baseURL = apiClient.defaults.baseURL;
    expect(baseURL).not.toContain("soal.help");
    expect(baseURL).not.toMatch(/^https?:\/\/(?!localhost|127\.0\.0\.1)/);
  });

  it("defaults to a safe same-origin or local API path", () => {
    const baseURL = apiClient.defaults.baseURL;
    expect(
      baseURL === "/api/v1" ||
        baseURL.startsWith("http://localhost") ||
        baseURL.startsWith("http://127.0.0.1")
    ).toBe(true);
  });

  describe("isApprovedBackendRequest", () => {
    it("approves internal relative paths", () => {
      expect(isApprovedBackendRequest({ url: "/auth/me" })).toBe(true);
      expect(isApprovedBackendRequest({ url: "/jobs" })).toBe(true);
    });

    it("rejects protocol-relative and untrusted third-party origins", () => {
      expect(isApprovedBackendRequest({ url: "//evil.com/steal" })).toBe(false);
      expect(isApprovedBackendRequest({ url: "https://attacker.com/api" })).toBe(false);
      expect(isApprovedBackendRequest({ url: "https://soal.help/api/v1" })).toBe(false);
    });
  });

  describe("request interceptor", () => {
    it("attaches Authorization: Bearer token to approved backend requests", async () => {
      authStorage.setToken("valid-jwt-token");
      const config = {
        url: "/auth/me",
        headers: {},
      };

      const intercepted = await apiClient.interceptors.request.handlers[0].fulfilled(config);
      expect(intercepted.headers.Authorization).toBe("Bearer valid-jwt-token");
    });

    it("never attaches Bearer token to unapproved external URLs", async () => {
      authStorage.setToken("valid-jwt-token");
      const config = {
        url: "https://untrusted-external-site.com/endpoint",
        headers: {},
      };

      const intercepted = await apiClient.interceptors.request.handlers[0].fulfilled(config);
      expect(intercepted.headers.Authorization).toBeUndefined();
    });

    it("strips legacy X-User-Id and X-Organization-Id headers", async () => {
      const config = {
        url: "/jobs",
        headers: {
          "X-User-Id": "forged-user-id",
          "X-Organization-Id": "forged-org-id",
        },
      };

      const intercepted = await apiClient.interceptors.request.handlers[0].fulfilled(config);
      expect(intercepted.headers["X-User-Id"]).toBeUndefined();
      expect(intercepted.headers["X-Organization-Id"]).toBeUndefined();
    });

    it("deletes Content-Type when request data is FormData so browser can set boundary", async () => {
      const formData = new FormData();
      formData.append("key", "val");
      const config = {
        url: "/candidates/1/resumes/upload",
        data: formData,
        headers: {
          "Content-Type": "multipart/form-data",
        },
      };

      const intercepted = await apiClient.interceptors.request.handlers[0].fulfilled(config);
      expect(intercepted.headers["Content-Type"]).toBeUndefined();
    });
  });

  describe("response interceptor error handling", () => {
    it("invokes unauthorizedHandler and clears token on 401 for business routes", async () => {
      authStorage.setToken("some-token");
      const handler = vi.fn();
      setUnauthorizedHandler(handler);

      const error = {
        config: { url: "/jobs" },
        response: { status: 401 },
      };

      const errorHandler = apiClient.interceptors.response.handlers[0].rejected;
      await expect(errorHandler(error)).rejects.toBe(error);

      expect(authStorage.getToken()).toBeNull();
      expect(handler).toHaveBeenCalledTimes(1);
    });

    it("does not invoke unauthorizedHandler on 401 for /auth/login (prevents redirect loop)", async () => {
      const handler = vi.fn();
      setUnauthorizedHandler(handler);

      const error = {
        config: { url: "/auth/login" },
        response: { status: 401 },
      };

      const errorHandler = apiClient.interceptors.response.handlers[0].rejected;
      await expect(errorHandler(error)).rejects.toBe(error);

      expect(handler).not.toHaveBeenCalled();
    });

    it("does not clear session or invoke unauthorizedHandler on 403 Forbidden", async () => {
      authStorage.setToken("active-token");
      const handler = vi.fn();
      setUnauthorizedHandler(handler);

      const error = {
        config: { url: "/settings/ai/api-key" },
        response: { status: 403 },
      };

      const errorHandler = apiClient.interceptors.response.handlers[0].rejected;
      await expect(errorHandler(error)).rejects.toBe(error);

      expect(authStorage.getToken()).toBe("active-token");
      expect(handler).not.toHaveBeenCalled();
    });
  });
});

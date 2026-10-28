import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "./apiClient";
import { getTalentPool } from "./talentPoolService";

vi.mock("./apiClient", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe("getTalentPool", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps rejected applications excluded by default", async () => {
    apiClient.get.mockResolvedValue({ data: [] });

    await getTalentPool();

    expect(apiClient.get).toHaveBeenCalledWith("/talent-pool", { params: {} });
  });

  it("requests rejected applications only when explicitly enabled", async () => {
    apiClient.get.mockResolvedValue({ data: [] });

    await getTalentPool({ includeRejected: true });

    expect(apiClient.get).toHaveBeenCalledWith("/talent-pool", {
      params: { include_rejected: true },
    });
  });

  it("creates a candidate-facing consent link with the token in the URL fragment", async () => {
    apiClient.post.mockResolvedValue({ data: { token: "opaque-token", expires_at: "2026-11-01T00:00:00Z" } });
    const { createTalentPoolConsentLink } = await import("./talentPoolService");

    const result = await createTalentPoolConsentLink("candidate-1");

    expect(apiClient.post).toHaveBeenCalledWith("/candidates/candidate-1/talent-pool-consent-link");
    expect(result.url).toBe(`${window.location.origin}/talent-pool/consent#opaque-token`);
    expect(result.expiresAt).toBe("2026-11-01T00:00:00Z");
  });
});

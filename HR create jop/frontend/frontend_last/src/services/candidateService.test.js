import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "./apiClient";
import { listCandidateProfiles, listCandidateResumes } from "./resumeService";
import { getCandidateById } from "./candidateService";

vi.mock("./apiClient", () => ({ default: { get: vi.fn() } }));
vi.mock("./resumeService", () => ({
  listCandidateProfiles: vi.fn(),
  listCandidateResumes: vi.fn(),
}));

describe("getCandidateById profile contact sources", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps CV-extracted contact separate from canonical candidate contact", async () => {
    apiClient.get.mockResolvedValue({
      data: {
        id: "candidate-1",
        full_name: "Ada Lovelace",
        email: null,
        phone: null,
        status: "active",
      },
    });
    listCandidateResumes.mockResolvedValue([{ id: "resume-1", created_at: "2026-10-01T00:00:00Z" }]);
    listCandidateProfiles.mockResolvedValue([
      {
        is_current: true,
        profile_data: { email: "ada.cv@example.com", phone: "+1 555 0100" },
      },
    ]);

    const candidate = await getCandidateById("candidate-1");

    expect(candidate.email).toBe("");
    expect(candidate.phone).toBe("");
    expect(candidate.profileEmail).toBe("ada.cv@example.com");
    expect(candidate.profilePhone).toBe("+1 555 0100");
  });
});

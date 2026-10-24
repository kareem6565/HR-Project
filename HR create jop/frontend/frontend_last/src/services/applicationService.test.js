import { afterEach, describe, expect, it, vi } from "vitest";
import apiClient from "./apiClient";
import { getApplications } from "./applicationService";

vi.mock("./apiClient", () => ({ default: { get: vi.fn() } }));

afterEach(() => vi.clearAllMocks());

describe("getApplications", () => {
  it("preserves the status query and maps the backend AI review group", async () => {
    apiClient.get.mockResolvedValue({
      data: [
        {
          id: "app-1",
          candidate_id: "candidate-1",
          candidate_name: "Ada Lovelace",
          job_id: "job-1",
          job_title: "Engineer",
          created_at: "2026-10-23T10:00:00Z",
          score: "81.579",
          group: "must_review",
          status: "analysis_pending",
        },
      ],
    });

    await expect(getApplications("analysis_pending")).resolves.toEqual([
      {
        id: "app-1",
        candidateId: "candidate-1",
        candidateName: "Ada Lovelace",
        job: "Engineer",
        appliedAt: "2026-10-23T10:00:00Z",
        score: "81.579",
        group: "must_review",
        status: "analysis_pending",
      },
    ]);
    expect(apiClient.get).toHaveBeenCalledWith("/job-applications", {
      params: { status: "analysis_pending" },
    });
  });
});

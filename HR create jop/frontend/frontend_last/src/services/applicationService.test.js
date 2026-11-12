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
          screening_status: "processing",
        },
      ],
    });

    await expect(getApplications("analysis_pending")).resolves.toEqual([
      {
        id: "app-1",
        candidateId: "candidate-1",
        candidateName: "Ada Lovelace",
        email: undefined,
        phone: undefined,
        job: "Engineer",
        jobId: "job-1",
        appliedAt: "2026-10-23T10:00:00Z",
        source: undefined,
        sourceMedium: undefined,
        sourceCampaign: undefined,
        score: "81.579",
        group: "must_review",
        status: "analysis_pending",
        screeningStatus: "processing",
        decisionStatus: "pending_review",
        decisionCreatedAt: undefined,
        evidence: [],
      },
    ]);
    expect(apiClient.get).toHaveBeenCalledWith("/job-applications", {
      params: { status: "analysis_pending" },
    });
  });

  it("maps paginated rows and sends server-side filters", async () => {
    apiClient.get.mockResolvedValue({ data: {
      items: [{ id: "app-1", candidate_name: "Ada", candidate_email: "ada@example.test", job_id: "job-1", job_title: "Engineer", screening_status: "processing", decision_status: "pending_review", source: "Referral" }],
      page: 2, page_size: 20, total: 21, pages: 2,
    } });
    await expect(getApplications({ search: "Ada", job_id: "job-1", page: 2, page_size: 20 })).resolves.toMatchObject({
      page: 2, pageSize: 20, total: 21, pages: 2,
      items: [{ candidateName: "Ada", email: "ada@example.test", jobId: "job-1", screeningStatus: "processing", decisionStatus: "pending_review", source: "Referral" }],
    });
    expect(apiClient.get).toHaveBeenCalledWith("/job-applications", {
      params: { search: "Ada", job_id: "job-1", page: 2, page_size: 20 },
    });
  });
});

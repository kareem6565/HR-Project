import { afterEach, describe, expect, it, vi } from "vitest";
import apiClient from "./apiClient";
import { getApplications } from "./applicationService";
import { getDashboardStats } from "./dashboardService";

vi.mock("./apiClient", () => ({ default: { get: vi.fn() } }));
vi.mock("./applicationService", () => ({ getApplications: vi.fn() }));

afterEach(() => vi.clearAllMocks());

describe("dashboard KPI definitions", () => {
  it("counts unique candidates with applications separately from application status counts", async () => {
    getApplications.mockResolvedValue([
      { candidateId: "candidate-a", status: "advanced" },
      { candidateId: "candidate-a", status: "ready_for_review" },
      { candidateId: "candidate-b", status: "created" },
      { candidateId: null, status: "advanced" },
    ]);
    apiClient.get.mockResolvedValue({
      data: [{ status: "active" }, { status: "closed" }, { status: "active" }],
    });

    await expect(getDashboardStats()).resolves.toEqual({
      candidatesWithApplications: 2,
      activeJobs: 2,
      applications: 4,
      shortlisted: 3,
      advancedApplications: 2,
    });
  });
});

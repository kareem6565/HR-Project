import { afterEach, describe, expect, it, vi } from "vitest";
import { getApplications } from "./applicationService";
import {
  filterApplicationsToLast30Days,
  filterApplicationsToRange,
  getAnalyticsSnapshot,
  getCandidateSources,
} from "./analyticsService";

vi.mock("./applicationService", () => ({ getApplications: vi.fn() }));

afterEach(() => vi.clearAllMocks());

const NOW = new Date("2026-10-23T12:00:00.000Z");
const app = (id, status, createdAt, score = null, candidateId = `candidate-${id}`) => ({
  id,
  candidateId,
  status,
  appliedAt: createdAt,
  score,
});

describe("period-scoped analytics", () => {
  it("includes exact period boundaries and excludes older, future, and invalid dates", () => {
    const lower30 = new Date(NOW.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
    const lower90 = new Date(NOW.getTime() - 90 * 24 * 60 * 60 * 1000).toISOString();
    const rows = [
      app("start30", "created", lower30),
      app("start90", "created", lower90),
      app("now", "advanced", NOW.toISOString()),
      app("old", "created", new Date(Date.parse(lower90) - 1).toISOString()),
      app("future", "created", new Date(NOW.getTime() + 1).toISOString()),
      app("invalid", "created", "not-a-date"),
    ];

    expect(filterApplicationsToLast30Days(rows, NOW).map((row) => row.id)).toEqual(["start30", "now"]);
    expect(filterApplicationsToRange(rows, "90d", NOW).map((row) => row.id)).toEqual([
      "start30", "start90", "now",
    ]);
  });

  it("uses one selected-period cohort for metrics, status shares, and weekly counts", async () => {
    getApplications.mockResolvedValue([
      app("1", "created", NOW.toISOString(), "40.000", "candidate-shared"),
      app("2", "advanced", NOW.toISOString(), "8e1", "candidate-shared"),
      app("3", "advanced", NOW.toISOString(), "101"),
      app("4", "unexpected_status", NOW.toISOString()),
      app("old", "created", new Date(NOW.getTime() - 31 * 24 * 60 * 60 * 1000).toISOString()),
      app("invalid", "created", "invalid"),
    ]);

    const result = await getAnalyticsSnapshot("30d", NOW);
    expect(getApplications).toHaveBeenCalledOnce();
    expect(result.metrics.find((metric) => metric.key === "applications")).toMatchObject({ value: 4 });
    expect(result.metrics.find((metric) => metric.key === "candidates")).toMatchObject({ value: 3 });
    expect(result.metrics.find((metric) => metric.key === "advanced_applications")).toMatchObject({ value: 2 });
    expect(result.metrics.find((metric) => metric.key === "avg_score").value).toBe("60%");
    expect(result.metrics.some((metric) => metric.key === "active_jobs")).toBe(false);
    expect(result.statusBreakdown.find((row) => row.stage === "Created")).toMatchObject({ count: 1, percent: 25 });
    expect(result.statusBreakdown.find((row) => row.stage === "Advanced")).toMatchObject({ count: 2, percent: 50 });
    expect(result.statusBreakdown.find((row) => row.stage === "Other statuses")).toMatchObject({ count: 1, percent: 25 });
    expect(result.statusBreakdown.reduce((sum, row) => sum + row.percent, 0)).toBeCloseTo(100, 8);
    expect(result.applicationTrend.reduce((sum, bucket) => sum + bucket.applications, 0)).toBe(4);
  });

  it("returns explicit zero shares for an empty period and marks sources unavailable", async () => {
    getApplications.mockResolvedValue([]);
    const result = await getAnalyticsSnapshot("90d", NOW);
    expect(result.statusBreakdown.every((row) => row.count === 0 && row.percent === 0)).toBe(true);
    expect(result.applicationTrend.every((bucket) => bucket.applications === 0)).toBe(true);
    expect(result.metrics.find((metric) => metric.key === "applications").label).toContain("last 90 days");
    await expect(getCandidateSources()).resolves.toBeNull();
  });

  it("keeps rounded status percentages totaling exactly 100", async () => {
    getApplications.mockResolvedValue([
      app("1", "created", NOW.toISOString()),
      app("2", "advanced", NOW.toISOString()),
      app("3", "rejected", NOW.toISOString()),
    ]);

    const result = await getAnalyticsSnapshot("30d", NOW);
    expect(result.statusBreakdown.reduce((sum, row) => sum + row.percent, 0)).toBeCloseTo(100, 8);
  });
});

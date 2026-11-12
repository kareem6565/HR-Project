import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import AnalyticsPage from "./AnalyticsPage";
import { getAnalyticsSnapshot } from "../../services/analyticsService";
import { getJobDistributionAnalytics } from "../../services/jobDistributionService";

vi.mock("../../services/analyticsService", () => ({
  getAnalyticsSnapshot: vi.fn(),
}));
vi.mock("../../services/jobDistributionService", () => ({ getJobDistributionAnalytics: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const snapshot = (range = "30d", count = 2) => ({
  range,
  metrics: [
    { key: "applications", label: `Applications · last ${range === "30d" ? 30 : 90} days`, value: count, deltaLabel: "created in selected period" },
  ],
  statusBreakdown: [
    { stage: "Created", count: 1, percent: 50 },
    { stage: "Advanced", count: 1, percent: 50 },
  ],
  applicationTrend: [{ label: "Oct 1", applications: count }],
});

describe("Analytics page", () => {
  it("shows campaign and source analytics alongside period-scoped hiring analysis", async () => {
    getAnalyticsSnapshot.mockResolvedValue(snapshot());
    getJobDistributionAnalytics.mockResolvedValue({
      campaigns: [{ distribution_id: "campaign-1", campaign_name: "Designer hiring", job_title: "Product Designer", channel: "linkedin", status: "shared", views: 12, applications: 3, conversion_percent: 25 }],
      sources: [{ source: "linkedin", medium: "social", applications: 3 }],
    });

    render(<AnalyticsPage />);

    expect(await screen.findByText("Hiring patterns and outcomes")).toBeTruthy();
    expect(screen.getByText("HERA · AI-ASSISTED, HR-LED")).toBeTruthy();
    expect(screen.getByText("Applications created by week")).toBeTruthy();
    expect(screen.getByText("Current application status")).toBeTruthy();
    expect(screen.getByText(/not stage-to-stage conversion rates/i)).toBeTruthy();
    expect(screen.getByText("Designer hiring")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("linkedin · social")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Last 30 days" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("reloads real analytics for the selected period", async () => {
    getAnalyticsSnapshot.mockImplementation(async (range) => snapshot(range));
    getJobDistributionAnalytics.mockResolvedValue({ campaigns: [], sources: [] });

    render(<AnalyticsPage />);
    await screen.findByText("Hiring patterns and outcomes");
    fireEvent.click(screen.getByRole("button", { name: "Last 90 days" }));

    expect(await screen.findByText("Applications · last 90 days")).toBeTruthy();
    expect(getAnalyticsSnapshot).toHaveBeenLastCalledWith("90d");
    expect(getJobDistributionAnalytics).toHaveBeenLastCalledWith(90);
    expect(screen.getByRole("button", { name: "Last 90 days" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("explains when the selected period contains no applications", async () => {
    getAnalyticsSnapshot.mockResolvedValue({
      range: "30d",
      metrics: [],
      statusBreakdown: [{ stage: "Created", count: 0, percent: 0 }],
      applicationTrend: [],
    });
    getJobDistributionAnalytics.mockResolvedValue({ campaigns: [], sources: [] });

    render(<AnalyticsPage />);

    expect(await screen.findByText("No application records were created in the last 30 days.")).toBeTruthy();
    expect(screen.getByText(/Status counts will appear when applications are created in this period/i)).toBeTruthy();
  });
});

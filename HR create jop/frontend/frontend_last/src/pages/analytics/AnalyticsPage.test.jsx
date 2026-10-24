import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import AnalyticsPage from "./AnalyticsPage";
import { getAnalyticsSnapshot, getCandidateSources } from "../../services/analyticsService";

vi.mock("../../services/analyticsService", () => ({
  getAnalyticsSnapshot: vi.fn(),
  getCandidateSources: vi.fn(),
}));

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
  it("shows HERA identity, period-scoped analysis, and honest source-data limitations", async () => {
    getAnalyticsSnapshot.mockResolvedValue(snapshot());
    getCandidateSources.mockResolvedValue(null);

    render(<AnalyticsPage />);

    expect(await screen.findByText("Hiring patterns and outcomes")).toBeTruthy();
    expect(screen.getByText("HERA · AI-ASSISTED, HR-LED")).toBeTruthy();
    expect(screen.getByText("Applications created by week")).toBeTruthy();
    expect(screen.getByText("Current application status")).toBeTruthy();
    expect(screen.getByText(/not stage-to-stage conversion rates/i)).toBeTruthy();
    expect(screen.getByText(/does not currently collect candidate-source data/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Last 30 days" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("reloads real analytics for the selected period", async () => {
    getAnalyticsSnapshot.mockImplementation(async (range) => snapshot(range));
    getCandidateSources.mockResolvedValue(null);

    render(<AnalyticsPage />);
    await screen.findByText("Hiring patterns and outcomes");
    fireEvent.click(screen.getByRole("button", { name: "Last 90 days" }));

    expect(await screen.findByText("Applications · last 90 days")).toBeTruthy();
    expect(getAnalyticsSnapshot).toHaveBeenLastCalledWith("90d");
    expect(screen.getByRole("button", { name: "Last 90 days" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("explains when the selected period contains no applications", async () => {
    getAnalyticsSnapshot.mockResolvedValue({
      range: "30d",
      metrics: [],
      statusBreakdown: [{ stage: "Created", count: 0, percent: 0 }],
      applicationTrend: [],
    });
    getCandidateSources.mockResolvedValue(null);

    render(<AnalyticsPage />);

    expect(await screen.findByText("No application records were created in the last 30 days.")).toBeTruthy();
    expect(screen.getByText(/Status counts will appear when applications are created in this period/i)).toBeTruthy();
  });
});

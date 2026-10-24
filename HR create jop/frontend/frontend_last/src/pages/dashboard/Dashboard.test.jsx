import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";
import {
  getApplicationsByJob,
  getDashboardStats,
} from "../../services/dashboardService";

vi.mock("../../services/dashboardService", () => ({
  getApplicationsByJob: vi.fn(),
  getDashboardStats: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Recruitment dashboard", () => {
  it("shows live overview values and describes application status rather than a funnel", async () => {
    getDashboardStats.mockResolvedValue({
      candidatesWithApplications: 12,
      activeJobs: 3,
      applications: 16,
      shortlisted: 4,
      advancedApplications: 2,
    });
    getApplicationsByJob.mockResolvedValue([{ job: "Product Designer", applications: 8 }]);

    render(<MemoryRouter><Dashboard /></MemoryRouter>);

    expect(await screen.findByText("A clearer view of your hiring activity")).toBeTruthy();
    expect(screen.getByText("HERA · AI-ASSISTED, HR-LED")).toBeTruthy();
    expect(screen.getByText("HERA · AI-ASSISTED, HR-LED").previousElementSibling.getAttribute("aria-hidden")).toBe("true");
    expect(screen.getByText("Live workspace snapshot")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Review applications/i }).getAttribute("href")).toBe("/applications");
    expect(screen.getByRole("link", { name: /Manage jobs/i }).getAttribute("href")).toBe("/jobs");
    expect(screen.getByText("Advanced applications")).toBeTruthy();
    expect(screen.getByText("Candidates with applications")).toBeTruthy();
    expect(screen.queryByText("Hired")).toBeNull();
    expect(screen.queryByText("Application status")).toBeNull();
    expect(screen.queryByText("Hiring funnel")).toBeNull();
    expect(getDashboardStats).toHaveBeenCalledOnce();
  });

  it("shows a useful empty state when there are no applications", async () => {
    getDashboardStats.mockResolvedValue({
      candidatesWithApplications: 0,
      activeJobs: 1,
      applications: 0,
      shortlisted: 0,
      advancedApplications: 0,
    });
    getApplicationsByJob.mockResolvedValue([]);

    render(<MemoryRouter><Dashboard /></MemoryRouter>);

    expect(await screen.findByText("No applications yet")).toBeTruthy();
    expect(screen.getByText(/their real application activity will appear here/i)).toBeTruthy();
  });
});

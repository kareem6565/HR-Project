import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
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
      totalJobs: 5,
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
    expect(screen.getByRole("link", { name: /Create vacancy/i }).getAttribute("href")).toBe("/jobs/new");
    const applicationLinks = screen.getAllByRole("link", { name: /Review applications/i });
    expect(applicationLinks).toHaveLength(2);
    expect(applicationLinks.every((link) => link.getAttribute("href") === "/applications")).toBe(true);
    expect(screen.getByRole("link", { name: /Manage jobs/i }).getAttribute("href")).toBe("/jobs");
    expect(screen.getByRole("img", { name: "Bar chart of applications for each job" })).toBeTruthy();
    expect(screen.getByRole("table", { name: "Application counts by job" })).toBeTruthy();
    expect(screen.getByRole("row", { name: "Product Designer 8" })).toBeTruthy();
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
      totalJobs: 1,
      applications: 0,
      shortlisted: 0,
      advancedApplications: 0,
    });
    getApplicationsByJob.mockResolvedValue([]);

    render(<MemoryRouter><Dashboard /></MemoryRouter>);

    expect(await screen.findByText("No applications yet")).toBeTruthy();
    expect(screen.getByText(/their real application activity will appear here/i)).toBeTruthy();
  });

  it("shows next actions when the recruiter has no organization records", async () => {
    getDashboardStats.mockResolvedValue({
      candidatesWithApplications: 0,
      activeJobs: 0,
      totalJobs: 0,
      applications: 0,
      advancedApplications: 0,
    });
    getApplicationsByJob.mockResolvedValue([]);
    render(<MemoryRouter><Dashboard /></MemoryRouter>);

    expect(await screen.findByText("No recruitment records in this workspace yet")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Create a vacancy" }).getAttribute("href")).toBe("/jobs/new");
    expect(screen.getByRole("link", { name: "Review candidates" }).getAttribute("href")).toBe("/candidates");
    expect(screen.getByRole("link", { name: "Open applications" }).getAttribute("href")).toBe("/applications");
  });
});

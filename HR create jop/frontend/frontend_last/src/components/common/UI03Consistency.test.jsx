import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { getTitleForPath } from "../../config/routes";
import Navbar from "../layout/Navbar";
import ErrorState from "./ErrorState";
import ApplicationsList from "../../pages/applications/ApplicationsList";
import JobsList from "../../pages/jobs/JobsList";
import ScreenCandidates from "../../pages/candidates/ScreenCandidates";
import * as applicationService from "../../services/applicationService";
import * as jobService from "../../services/jobService";
import { AuthProvider } from "../../context/AuthContext";

vi.mock("../../services/applicationService", () => ({
  getApplications: vi.fn(),
}));

vi.mock("../../services/jobService", () => ({
  getJobs: vi.fn(),
  deleteJob: vi.fn(),
}));

describe("UI-03: Route Titles from Single Map", () => {
  it("resolves accurate titles for registered routes and sub-routes", () => {
    expect(getTitleForPath("/dashboard")).toBe("Dashboard");
    expect(getTitleForPath("/jobs")).toBe("Jobs");
    expect(getTitleForPath("/jobs/new")).toBe("Create Job");
    expect(getTitleForPath("/jobs/job-123/edit")).toBe("Edit Job");
    expect(getTitleForPath("/jobs/job-123")).toBe("Job Details");
    expect(getTitleForPath("/candidates")).toBe("Candidates");
    expect(getTitleForPath("/candidates/screen")).toBe("Screen Candidates");
    expect(getTitleForPath("/candidates/cand-456")).toBe("Candidate Details");
    expect(getTitleForPath("/evaluations")).toBe("Applications");
    expect(getTitleForPath("/applications")).toBe("Applications");
    expect(getTitleForPath("/applications/app-789/review")).toBe("Application Review");
    expect(getTitleForPath("/applications/app-789/questions")).toBe("Question Set Builder");
    expect(getTitleForPath("/talent-pool")).toBe("Talent Pool");
    expect(getTitleForPath("/matching-results")).toBe("Matching Results");
    expect(getTitleForPath("/analytics")).toBe("Analytics");
    expect(getTitleForPath("/settings")).toBe("AI Settings");
    expect(getTitleForPath("/interviews")).toBe("Interviews");
    expect(getTitleForPath("/interviews/schedule")).toBe("Schedule Interview");
    expect(getTitleForPath("/interviews/int-1/feedback")).toBe("Interview Feedback");
    expect(getTitleForPath("/interview-questions")).toBe("Interview Questions");
    expect(getTitleForPath("/ai-activity")).toBe("AI Activity");
    expect(getTitleForPath("/unknown-page")).toBe("Overview");
  });
});

describe("UI-03: Navbar Dead Control Removal", () => {
  it("does not render any inert notification bell button in Navbar", () => {
    render(
      <AuthProvider>
        <Navbar pathname="/dashboard" />
      </AuthProvider>
    );

    // Page title is accurately rendered
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Dashboard");

    // Notification bell is removed to eliminate dead control
    expect(screen.queryByLabelText(/notifications/i)).not.toBeInTheDocument();
  });
});

describe("UI-03: Null Score Display", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a dash for null application score and never displays 'null%'", async () => {
    applicationService.getApplications.mockResolvedValue([
      {
        id: "app-1",
        candidateName: "Ada Lovelace",
        job: "Software Engineer",
        appliedAt: "2025-01-10",
        score: null,
        status: "ready_for_review",
      },
      {
        id: "app-2",
        candidateName: "Alan Turing",
        job: "Cryptanalyst",
        appliedAt: "2025-01-11",
        score: 88,
        status: "advanced",
      },
    ]);

    render(
      <MemoryRouter>
        <ApplicationsList />
      </MemoryRouter>
    );

    await screen.findByText("Ada Lovelace");

    // Null score is rendered as dash "—", Alan's score is "88%"
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("88%")).toBeInTheDocument();
    expect(screen.queryByText(/null%/i)).not.toBeInTheDocument();
  });
});

describe("UI-03: Job Delete Confirmation Modal and Inline Error State", () => {
  const mockJob = {
    id: "job-1",
    title: "Platform Architect",
    department: "Infrastructure",
    location: "Remote",
    status: "active",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    jobService.getJobs.mockResolvedValue([mockJob]);
  });

  it("opens shared confirmation modal and performs deletion without window.confirm or window.alert", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    const alertSpy = vi.spyOn(window, "alert");
    jobService.deleteJob.mockResolvedValue({});

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <JobsList />
      </MemoryRouter>
    );

    await screen.findByText("Platform Architect");

    // Heading hierarchy: h2 for section head
    expect(screen.getByRole("heading", { level: 2, name: /open positions/i })).toBeInTheDocument();

    // Click delete trash icon
    await user.click(screen.getByRole("button", { name: `Delete ${mockJob.title}` }));

    // Confirmation modal opens with dialog semantics
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Are you sure you want to delete/i)).toBeInTheDocument();

    // Confirm button in modal
    await user.click(screen.getByRole("button", { name: "Delete Job" }));

    await waitFor(() => {
      expect(jobService.deleteJob).toHaveBeenCalledWith("job-1");
    });

    // Native dialogs were NOT invoked
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(alertSpy).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
    alertSpy.mockRestore();
  });

  it("displays inline error in modal when deleteJob fails", async () => {
    const alertSpy = vi.spyOn(window, "alert");
    jobService.deleteJob.mockRejectedValue({
      response: { data: { detail: "Job has active applications and cannot be deleted." } },
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <JobsList />
      </MemoryRouter>
    );

    await screen.findByText("Platform Architect");
    await user.click(screen.getByRole("button", { name: `Delete ${mockJob.title}` }));

    await user.click(screen.getByRole("button", { name: "Delete Job" }));

    // Inline error displayed inside modal
    await screen.findByRole("alert");
    expect(screen.getByText("Job has active applications and cannot be deleted.")).toBeInTheDocument();
    expect(alertSpy).not.toHaveBeenCalled();
    alertSpy.mockRestore();
  });
});

describe("UI-03: Shared Button in ErrorState", () => {
  it("renders retry button using shared Button with btn btn-primary styling", async () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Connection lost" onRetry={onRetry} />);

    const button = screen.getByRole("button", { name: /try again/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass("btn", "btn-primary");
  });
});

describe("UI-03: Misleading Progress Chip Removal", () => {
  it("does not render misleading 1 / 2 progress chip in ScreenCandidates", async () => {
    jobService.getJobs.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Create Screening");
    expect(screen.queryByText("1 / 2")).not.toBeInTheDocument();
  });
});

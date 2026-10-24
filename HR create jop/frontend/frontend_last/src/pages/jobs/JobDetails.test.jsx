import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import JobDetails from "./JobDetails";
import { deleteJob, getJobById, updateJob } from "../../services/jobService";
import { approveJobProfile, extractJobProfile, listJobProfiles } from "../../services/jobProfileService";

vi.mock("../../services/jobService", () => ({
  getJobById: vi.fn(),
  deleteJob: vi.fn(),
  updateJob: vi.fn(),
}));

vi.mock("../../services/jobProfileService", () => ({
  listJobProfiles: vi.fn(),
  extractJobProfile: vi.fn(),
  approveJobProfile: vi.fn(),
}));

function RouteProbe() {
  const location = useLocation();
  return <p>Route: {location.pathname}</p>;
}

const job = {
  id: "job-1",
  title: "Senior Engineer",
  status: "active",
  description: "Build reliable services.\n- 5 years of experience\n- Collaborate across teams\nSkills: TypeScript\nSkills: React",
  department: "Engineering",
  location: "Cairo, Egypt",
  type: "Full-time",
  experience: "5+ years",
  requirements: ["5 years of experience", "Collaborate across teams"],
  requiredSkills: ["TypeScript", "React"],
  applicants: 2,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/jobs/job-1"]}>
      <Routes>
        <Route path="/jobs/:id" element={<JobDetails />} />
        <Route path="/jobs" element={<RouteProbe />} />
        <Route path="/jobs/:id/edit" element={<RouteProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  getJobById.mockResolvedValue(job);
  listJobProfiles.mockResolvedValue([]);
  updateJob.mockImplementation((_id, updates) => Promise.resolve({ ...job, ...updates }));
  deleteJob.mockResolvedValue({ success: true });
  extractJobProfile.mockResolvedValue({});
  approveJobProfile.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("JobDetails", () => {
  it("shows role information once and separates the persisted description suffix", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Senior Engineer" })).toBeInTheDocument();
    expect(screen.getByText("Build reliable services.")).toBeInTheDocument();
    expect(screen.getAllByText("5 years of experience")).toHaveLength(1);
    expect(screen.getAllByText("Collaborate across teams")).toHaveLength(1);
    expect(screen.getAllByText("TypeScript")).toHaveLength(1);
    expect(screen.getByText("2 candidates applied")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Senior Engineer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete Senior Engineer" })).toBeInTheDocument();
  });

  it("provides a retry state when loading the job request fails", async () => {
    getJobById.mockRejectedValueOnce(new Error("network error")).mockResolvedValueOnce(job);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load this job");
    await user.click(screen.getByRole("button", { name: /Try again/i }));
    expect(await screen.findByRole("heading", { name: "Senior Engineer" })).toBeInTheDocument();
    expect(getJobById).toHaveBeenCalledTimes(2);
  });

  it("preserves the existing status update behavior", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Close/i }));
    await waitFor(() => expect(updateJob).toHaveBeenCalledWith("job-1", { status: "closed" }));
    expect(await screen.findByText("Closed")).toBeInTheDocument();
  });

  it("keeps the accessible delete confirmation and navigates after success", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Delete Senior Engineer" }));
    expect(screen.getByRole("dialog", { name: "Delete Job: Senior Engineer" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete Job" }));
    await waitFor(() => expect(deleteJob).toHaveBeenCalledWith("job-1"));
    expect(await screen.findByText("Route: /jobs")).toBeInTheDocument();
  });

  it("explains the empty job profile and leaves extraction an explicit user action", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText(/HERA can extract a structured draft/i)).toBeInTheDocument();
    expect(extractJobProfile).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Run AI extraction" }));
    await waitFor(() => expect(extractJobProfile).toHaveBeenCalledWith("job-1"));
    expect(approveJobProfile).not.toHaveBeenCalled();
  });

  it("shows source-grounded quality findings as advisory questions for HR", async () => {
    listJobProfiles.mockResolvedValueOnce([
      {
        id: "profile-1",
        version_number: 1,
        source: "ai_extracted",
        status: "draft",
        is_current: true,
        profile_data: {
          title: "Senior Engineer",
          requirements: [],
          quality_review: {
            status: "verified",
            findings: [
              {
                finding_type: "not_measurable",
                source_quote: "Build reliable services.",
                concern: "The expected reliability level is not specified.",
                question_for_hr: "What reliability target should candidates meet?",
              },
            ],
          },
        },
      },
    ]);
    renderPage();

    expect(await screen.findByRole("region", { name: "Job description quality review" }))
      .toBeInTheDocument();
    expect(screen.getAllByText("Build reliable services.")).toHaveLength(2);
    expect(screen.getByText("What reliability target should candidates meet?"))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("truthfully explains when a quality review is unavailable", async () => {
    listJobProfiles.mockResolvedValueOnce([
      {
        id: "profile-legacy",
        version_number: 1,
        source: "ai_extracted",
        status: "draft",
        is_current: true,
        profile_data: { title: "Senior Engineer", requirements: [] },
      },
    ]);
    renderPage();

    expect(
      await screen.findByText(/A quality review was not returned/i)
    ).toBeInTheDocument();
  });

  it("distinguishes unavailable profile data from an empty profile list", async () => {
    listJobProfiles.mockRejectedValueOnce(new Error("network error")).mockResolvedValueOnce([]);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load job profiles");
    expect(screen.queryByText("No job profile yet")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reload profile data" }));
    expect(await screen.findByText("No job profile yet")).toBeInTheDocument();
    expect(listJobProfiles).toHaveBeenCalledTimes(2);
  });
});

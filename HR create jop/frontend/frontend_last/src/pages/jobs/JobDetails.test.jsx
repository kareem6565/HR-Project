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

    expect(await screen.findByText(/Analyze the job description to create a draft/i)).toBeInTheDocument();
    expect(extractJobProfile).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Analyze with HERA" }));
    await waitFor(() => expect(extractJobProfile).toHaveBeenCalledWith("job-1"));
    expect(approveJobProfile).not.toHaveBeenCalled();
  });

  it("keeps quality findings collapsed until HR chooses to review them", async () => {
    const user = userEvent.setup();
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
    const { container } = renderPage();

    await screen.findByRole("heading", { name: "Senior Engineer" });
    const qualityDisclosure = container.querySelector(".job-quality-disclosure");
    expect(qualityDisclosure).not.toHaveAttribute("open");
    await user.click(qualityDisclosure.querySelector("summary"));
    expect(await screen.findByRole("region", { name: "Job description quality review" }))
      .toBeInTheDocument();
    expect(screen.getAllByText("Build reliable services.")).toHaveLength(2);
    expect(screen.getByText("What reliability target should candidates meet?"))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("shows each supported quality finding type while keeping approval an HR action", async () => {
    const user = userEvent.setup();
    listJobProfiles.mockResolvedValueOnce([
      {
        id: "profile-quality-types",
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
                finding_type: "unclear_requirement",
                source_quote: "Experience with backend systems.",
                concern: "The experience scope is unclear.",
                question_for_hr: "Which backend systems are relevant?",
              },
              {
                finding_type: "potential_conflict",
                source_quote: "Five years required; graduates with no experience welcome.",
                concern: "These experience expectations may conflict.",
                question_for_hr: "Which experience level should apply?",
              },
              {
                finding_type: "priority_unclear",
                source_quote: "Python is both essential and preferred.",
                concern: "The priority is unclear.",
                question_for_hr: "Is Python essential?",
              },
              {
                finding_type: "not_measurable",
                source_quote: "Build reliable services.",
                concern: "Reliability is not measurable here.",
                question_for_hr: "What reliability target is expected?",
              },
            ],
          },
        },
      },
    ]);
    renderPage();

    await screen.findByRole("heading", { name: "Senior Engineer" });
    const disclosure = document.querySelector(".job-quality-disclosure");
    await user.click(disclosure.querySelector("summary"));

    expect(await screen.findByText("Unclear requirement")).toBeInTheDocument();
    expect(screen.getByText("Potential conflict")).toBeInTheDocument();
    expect(screen.getByText("Priority may be unclear")).toBeInTheDocument();
    expect(screen.getByText("Hard to measure")).toBeInTheDocument();
    expect(screen.getByText("Which backend systems are relevant?")).toBeInTheDocument();
    const approveButton = screen.getByRole("button", { name: "Approve" });
    expect(approveButton).toBeInTheDocument();
    expect(approveJobProfile).not.toHaveBeenCalled();

    await user.click(approveButton);
    await waitFor(() => expect(approveJobProfile).toHaveBeenCalledWith("profile-quality-types"));
  });

  it("truthfully explains when a quality review is unavailable", async () => {
    const user = userEvent.setup();
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
    const { container } = renderPage();

    await screen.findByRole("heading", { name: "Senior Engineer" });
    await user.click(container.querySelector(".job-quality-disclosure summary"));
    expect(
      await screen.findByText(/A quality review was not returned/i)
    ).toBeInTheDocument();
  });

  it("explains partial quote verification and displays only the returned verified finding", async () => {
    const user = userEvent.setup();
    listJobProfiles.mockResolvedValueOnce([
      {
        id: "profile-partial-quality",
        version_number: 1,
        source: "ai_extracted",
        status: "draft",
        is_current: true,
        profile_data: {
          title: "Senior Engineer",
          requirements: [],
          quality_review: {
            status: "partially_verified",
            findings: [
              {
                finding_type: "not_measurable",
                source_quote: "Build reliable services.",
                concern: "The expected reliability level is unspecified.",
                question_for_hr: "What reliability target should apply?",
              },
            ],
          },
        },
      },
    ]);
    const { container } = renderPage();

    await screen.findByRole("heading", { name: "Senior Engineer" });
    await user.click(container.querySelector(".job-quality-disclosure summary"));

    expect(await screen.findByRole("status")).toHaveTextContent(/Some findings were omitted/i);
    const qualityReview = screen.getByRole("region", { name: "Job description quality review" });
    expect(qualityReview.querySelector("blockquote")).toHaveTextContent("Build reliable services.");
    expect(screen.getByText("What reliability target should apply?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(approveJobProfile).not.toHaveBeenCalled();
  });

  it("shows HR-provided source details without claiming HERA verified availability", async () => {
    listJobProfiles.mockResolvedValueOnce([
      {
        id: "profile-source",
        version_number: 1,
        source: "hr_edited",
        status: "draft",
        is_current: true,
        profile_data: { title: "Senior Engineer", requirements: [] },
        raw_input_snapshot: { original_listing_text: "Original synthetic listing text." },
        provenance: {
          source: {
            source_name: "Synthetic careers page",
            source_url: "https://example.test/jobs/role",
            reviewed_at: "2026-10-25T10:00:00+00:00",
            reviewed_by_user_id: "user-1",
            availability_checked_by_hera: false,
          },
          field_origins: {
            title: "hr_edited_after_hera_suggestion",
          },
        },
      },
    ]);
    const user = userEvent.setup();
    renderPage();

    const summary = await screen.findByText("Listing source · reviewed by HR");
    await user.click(summary);
    expect(screen.getByText(/HERA has not checked whether either link works/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open provided source link" })).toHaveAttribute(
      "href",
      "https://example.test/jobs/role"
    );
    await user.click(screen.getByText("View original listing text provided by HR"));
    expect(screen.getByText("Original synthetic listing text.")).toBeInTheDocument();
    await user.click(screen.getByText("How these fields were prepared"));
    expect(screen.getByText(/Suggested by HERA, then reviewed or edited by HR/)).toBeInTheDocument();
  });

  it("shows the current profile first and collapses excess summary, requirements, and older versions", async () => {
    const user = userEvent.setup();
    const longSummary = "A carefully scoped role summary that stays readable in its preview. ".repeat(5);
    listJobProfiles.mockResolvedValueOnce([
      {
        id: "profile-1",
        version_number: 1,
        source: "ai_extracted",
        status: "approved",
        is_current: false,
        profile_data: {
          title: "Earlier Engineer Profile",
          summary: "An older saved summary.",
          requirements: [],
        },
      },
      {
        id: "profile-2",
        version_number: 2,
        source: "ai_extracted",
        status: "approved",
        is_current: true,
        profile_data: {
          title: "Current Engineer Profile",
          summary: longSummary,
          requirements: [
            { key: "must-1", text: "Must have evidence", category: "must_have" },
            { key: "must-2", text: "Must have experience", category: "must_have" },
            { key: "other-1", text: "Preferred criterion one", category: "important" },
            { key: "other-2", text: "Preferred criterion two", category: "important" },
            { key: "other-3", text: "Preferred criterion three", category: "important" },
          ],
          quality_review: { status: "verified", findings: [] },
        },
      },
    ]);
    renderPage();

    expect(await screen.findByText("Current Engineer Profile")).toBeInTheDocument();
    expect(screen.getByText("Must have evidence · must have")).toBeInTheDocument();
    expect(screen.getByText("Must have experience · must have")).toBeInTheDocument();
    expect(screen.getByText(/View all 5 requirements \(1 more\)/)).toBeInTheDocument();
    expect(screen.getByText("Previous versions (1)").closest("details")).not.toHaveAttribute("open");

    const summaryDisclosure = screen.getByText("Read full summary").closest("details");
    expect(summaryDisclosure).not.toHaveAttribute("open");
    await user.click(summaryDisclosure.querySelector("summary"));
    expect(summaryDisclosure).toHaveAttribute("open");

    await user.click(screen.getByText("Previous versions (1)").closest("summary"));
    expect(await screen.findByText("Earlier Engineer Profile")).toBeInTheDocument();
    expect(approveJobProfile).not.toHaveBeenCalled();
  });

  it("distinguishes unavailable profile data from an empty profile list", async () => {
    listJobProfiles.mockRejectedValueOnce(new Error("network error")).mockResolvedValueOnce([]);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load job profiles");
    expect(screen.queryByText("No structured profile yet")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reload profile data" }));
    expect(await screen.findByText("No structured profile yet")).toBeInTheDocument();
    expect(listJobProfiles).toHaveBeenCalledTimes(2);
  });
});

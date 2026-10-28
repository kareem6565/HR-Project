import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";

import {
  createJob,
  getJobById,
  suggestJobDraft,
  updateJob,
} from "../../services/jobService";
import { createJobProfile, extractJobProfile, listJobProfiles } from "../../services/jobProfileService";
import JobForm from "./JobForm";

vi.mock("../../services/jobService", () => ({
  createJob: vi.fn(),
  getJobById: vi.fn(),
  suggestJobDraft: vi.fn(),
  updateJob: vi.fn(),
}));

vi.mock("../../services/jobProfileService", () => ({
  createJobProfile: vi.fn(),
  extractJobProfile: vi.fn(),
  listJobProfiles: vi.fn(),
}));

const DEFAULT_SUGGESTION = {
  title: "Backend Engineer",
  department: "engineering",
  location: "Remote",
  type: "Contract",
  experience: "5+ years",
  requirements: ["Design APIs", "Write tests"],
  requiredSkills: ["Python", "FastAPI"],
};

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-path">{location.pathname}</div>;
}

function renderForm(initialPath = "/jobs/new") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/jobs/new" element={<JobForm />} />
        <Route path="/jobs/:id/edit" element={<JobForm />} />
        <Route path="/jobs/:id" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

function formChips(container) {
  return container.querySelector("form").querySelectorAll(".ai-chip").length;
}

describe("JobForm AI-assisted creation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getJobById.mockResolvedValue(null);
    suggestJobDraft.mockResolvedValue({ ...DEFAULT_SUGGESTION });
    listJobProfiles.mockResolvedValue([]);
    createJobProfile.mockResolvedValue({ id: "source-profile" });
  });

  test("uses a single-column form layout instead of an empty grid column", async () => {
    const { container } = renderForm();

    await screen.findByRole("heading", { name: "Create New Job" });
    expect(container.querySelector("section.job-form-grid")).toBeInTheDocument();
  });

  test("sends only the raw description to the auto-fill endpoint", async () => {
    renderForm();
    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/Description/),
      "Backend Engineer, engineering, remote, 5+ years, Python"
    );
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));

    await waitFor(() => expect(suggestJobDraft).toHaveBeenCalledTimes(1));
    expect(suggestJobDraft).toHaveBeenCalledWith(
      "Backend Engineer, engineering, remote, 5+ years, Python"
    );
  });

  test("fills empty fields from HERA suggestions and tags them with an AI chip", async () => {
    const { container } = renderForm();
    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/Description/),
      "Backend Engineer, engineering, remote, 5+ years, Python"
    );
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));

    await waitFor(() => expect(suggestJobDraft).toHaveBeenCalled());
    expect(screen.getByLabelText(/Job Title/)).toHaveValue("Backend Engineer");
    expect(screen.getByLabelText(/Department/)).toHaveValue("engineering");
    expect(screen.getByLabelText(/Location/)).toHaveValue("Remote");
    expect(screen.getByLabelText(/Employment Type/)).toHaveValue("Contract");
    expect(screen.getByLabelText(/Experience/)).toHaveValue("5+ years");
    expect(screen.getByLabelText(/Requirements/)).toHaveDisplayValue("Design APIs\nWrite tests");
    expect(screen.getByLabelText(/Required Skills/)).toHaveDisplayValue("Python, FastAPI");
    expect(formChips(container)).toBe(7);
    expect(screen.getByRole("status").textContent).toContain("HERA suggested values");
  });

  test("does not overwrite fields the user already typed", async () => {
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Job Title/), "My Custom Title");
    await user.type(
      screen.getByLabelText(/Description/),
      "Backend Engineer, engineering, remote, 5+ years, Python"
    );
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));

    await waitFor(() => expect(suggestJobDraft).toHaveBeenCalled());
    expect(screen.getByLabelText(/Job Title/)).toHaveValue("My Custom Title");
    expect(screen.getByLabelText(/Department/)).toHaveValue("engineering");
  });

  test("editing an AI-suggested field clears its AI chip", async () => {
    const { container } = renderForm();
    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/Description/),
      "Backend Engineer, engineering, remote, 5+ years, Python"
    );
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));
    await waitFor(() => expect(formChips(container)).toBe(7));

    const department = screen.getByLabelText(/Department/);
    await user.type(department, "Platform");

    expect(formChips(container)).toBe(6);
  });

  test("keeps inputs intact and reports the error when HERA is unreachable", async () => {
    suggestJobDraft.mockRejectedValue(new Error("Network down"));
    const { container } = renderForm();
    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/Description/),
      "Backend Engineer"
    );
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/entries are unchanged/i));
    expect(screen.getByRole("alert")).not.toHaveTextContent(/Network down/);
    expect(screen.getByLabelText(/Job Title/)).toHaveValue("");
    expect(formChips(container)).toBe(0);
  });

  test("reports when HERA detected nothing new to fill", async () => {
    suggestJobDraft.mockResolvedValue({
      title: "",
      department: "",
      location: "",
      type: "",
      experience: "",
      requirements: [],
      requiredSkills: [],
    });
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Description/), "A vague listing");
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/could not suggest values/i));
    expect(screen.getByLabelText(/Job Title/)).toHaveValue("");
  });

  test("preserves edits made while a HERA suggestion request is pending", async () => {
    let resolveSuggestion;
    suggestJobDraft.mockReturnValue(new Promise((resolve) => { resolveSuggestion = resolve; }));
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Description/), "Backend Engineer role");
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));
    await user.type(screen.getByLabelText(/Job Title/), "My title while HERA reads");

    resolveSuggestion({ ...DEFAULT_SUGGESTION });

    await waitFor(() => expect(screen.getByLabelText(/Department/)).toHaveValue("engineering"));
    expect(screen.getByLabelText(/Job Title/)).toHaveValue("My title while HERA reads");
  });

  test("does not apply suggestions from a description changed while the request is pending", async () => {
    let resolveSuggestion;
    suggestJobDraft.mockReturnValue(new Promise((resolve) => { resolveSuggestion = resolve; }));
    renderForm();
    const user = userEvent.setup();
    const description = screen.getByLabelText(/Description/);

    await user.type(description, "Old role details");
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));
    await user.clear(description);
    await user.type(description, "Updated role details");
    resolveSuggestion({ ...DEFAULT_SUGGESTION });

    expect(await screen.findByText(/description changed/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Job Title/)).toHaveValue("");
  });

  test("preserves an explicitly selected Full-time employment type", async () => {
    renderForm();
    const user = userEvent.setup();
    const employmentType = screen.getByLabelText(/Employment Type/);

    await user.selectOptions(employmentType, "Part-time");
    await user.selectOptions(employmentType, "Full-time");
    await user.type(screen.getByLabelText(/Description/), "Contract Backend Engineer");
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));

    await waitFor(() => expect(suggestJobDraft).toHaveBeenCalled());
    expect(employmentType).toHaveValue("Full-time");
  });

  test("explains when all fillable fields already have values", async () => {
    renderForm();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Job Title/), "Backend Engineer");
    await user.type(screen.getByLabelText(/Department/), "Engineering");
    await user.type(screen.getByLabelText(/Location/), "Remote");
    await user.selectOptions(screen.getByLabelText(/Employment Type/), "Contract");
    await user.type(screen.getByLabelText(/Experience/), "5 years");
    await user.type(screen.getByLabelText(/Description/), "Role description");
    await user.type(screen.getByLabelText(/Requirements/), "Build APIs");
    await user.type(screen.getByLabelText(/Required Skills/), "Python");
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));

    expect(await screen.findByRole("status")).toHaveTextContent(/no blank fields/i);
    expect(suggestJobDraft).not.toHaveBeenCalled();
  });

  test("saving a job keeps the form open; Analyze navigates to the job review", async () => {
    createJob.mockResolvedValue({ id: "job-abc" });
    extractJobProfile.mockResolvedValue({ profile_id: "profile-1" });
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Job Title/), "Backend Engineer");
    await user.type(screen.getByLabelText(/Description/), "Build APIs in Python.");
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(createJob).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Analyze with HERA" })).toBeInTheDocument();
    expect(screen.queryByTestId("location-path")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Analyze with HERA" }));

    await waitFor(() => expect(extractJobProfile).toHaveBeenCalledWith("job-abc"));
    await waitFor(() =>
      expect(screen.getByTestId("location-path")).toHaveTextContent("/jobs/job-abc")
    );
  });

  test("job create payload carries only job form fields (no scoring or confidence)", async () => {
    createJob.mockResolvedValue({ id: "job-abc" });
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Job Title/), "Backend Engineer");
    await user.type(screen.getByLabelText(/Description/), "Build APIs in Python.");
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(createJob).toHaveBeenCalledTimes(1));
    const payload = createJob.mock.calls[0][0];
    expect(Object.keys(payload).sort()).toEqual(
      [
        "title",
        "department",
        "location",
        "type",
        "experience",
        "status",
        "description",
        "requirements",
        "requiredSkills",
      ].sort()
    );
    expect(payload).not.toHaveProperty("confidence");
    expect(payload).not.toHaveProperty("score");
    expect(payload).not.toHaveProperty("match_percent");
  });

  test("persists reviewed source metadata separately and keeps human edits after failed analysis", async () => {
    createJob.mockResolvedValue({ id: "job-source" });
    extractJobProfile.mockRejectedValue(new Error("Provider unavailable"));
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Description/), "Synthetic role listing with Python experience.");
    await user.type(screen.getByLabelText("Job Title"), "HR's backend title");
    await user.type(screen.getByLabelText("Source name"), "Synthetic careers page");
    await user.type(screen.getByLabelText("Source link"), "https://example.test/roles/backend");
    await user.click(screen.getByLabelText(/I reviewed these source details/));
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(createJobProfile).toHaveBeenCalledTimes(1));
    expect(createJob.mock.calls[0][0].title).toBe("HR's backend title");
    const profilePayload = createJobProfile.mock.calls[0][1];
    expect(profilePayload.source_metadata.source_name).toBe("Synthetic careers page");
    expect(profilePayload.source_metadata.review_confirmed).toBe(true);
    expect(profilePayload.source_original_listing_text).toBe("Synthetic role listing with Python experience.");
    expect(profilePayload.profile_data.title).toBe("HR's backend title");
    expect(profilePayload.field_origins.title).toBe("hr_entered_or_edited");

    await user.click(screen.getByRole("button", { name: "Analyze with HERA" }));
    expect(await screen.findByText(/Provider unavailable/)).toBeInTheDocument();
    expect(screen.getByLabelText("Job Title")).toHaveValue("HR's backend title");
    expect(createJobProfile).toHaveBeenCalledTimes(1);
  });

  test("records HR edits made over HERA suggestions without replacing them silently", async () => {
    createJob.mockResolvedValue({ id: "job-origin" });
    renderForm();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Description/), "Backend engineer, Python and FastAPI.");
    await user.type(screen.getByLabelText("Source name"), "Synthetic source");
    await user.click(screen.getByLabelText(/I reviewed these source details/));
    await user.click(screen.getByRole("button", { name: /Suggest fields with HERA/ }));
    await waitFor(() => expect(screen.getByLabelText(/Job Title/)).toHaveValue("Backend Engineer"));
    await user.clear(screen.getByLabelText(/Job Title/));
    await user.type(screen.getByLabelText(/Job Title/), "HR reviewed title");
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(createJobProfile).toHaveBeenCalled());
    const profilePayload = createJobProfile.mock.calls[0][1];
    expect(profilePayload.profile_data.title).toBe("HR reviewed title");
    expect(profilePayload.field_origins.title).toBe("hr_edited_after_hera_suggestion");
  });

  test("edit mode preloads the job and offers Analyze immediately", async () => {
    getJobById.mockResolvedValue({
      id: "job-1",
      title: "Existing Role",
      status: "draft",
      description: "Some raw description",
      department: "",
      location: "",
      type: "Full-time",
      experience: "",
      requirements: [],
      requiredSkills: [],
    });
    updateJob.mockResolvedValue({ id: "job-1" });
    extractJobProfile.mockResolvedValue({ profile_id: "profile-1" });
renderForm("/jobs/job-1/edit");
    const user = userEvent.setup();

    expect(await screen.findByLabelText(/Job Title/)).toHaveValue("Existing Role");
    expect(screen.getByRole("button", { name: "Analyze with HERA" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Analyze with HERA" }));
    await waitFor(() => expect(extractJobProfile).toHaveBeenCalledWith("job-1"));
    await waitFor(() =>
      expect(screen.getByTestId("location-path")).toHaveTextContent("/jobs/job-1")
    );
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";

import {
  createJob,
  getJobById,
  suggestJobDraft,
  uploadJobSourceFile,
  updateJob,
} from "../../services/jobService";
import {
  buildJobDescription,
  createJobProfile,
  extractJobProfile,
  getLinkedInJobImport,
  startLinkedInJobImport,
} from "../../services/jobProfileService";
import JobForm from "./JobForm";

vi.mock("../../services/jobService", () => ({
  createJob: vi.fn(),
  getJobById: vi.fn(),
  suggestJobDraft: vi.fn(),
  uploadJobSourceFile: vi.fn(),
  updateJob: vi.fn(),
}));

vi.mock("../../services/jobProfileService", () => ({
  buildJobDescription: vi.fn(),
  createJobProfile: vi.fn(),
  extractJobProfile: vi.fn(),
  getLinkedInJobImport: vi.fn(),
  startLinkedInJobImport: vi.fn(),
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
    buildJobDescription.mockResolvedValue({
      schema_version: "1.4",
      title: "Backend Engineer",
      summary: "Build reliable backend services.",
      requirements: [
        { text: "Python", category: "must_have", dimension: "skill" },
        { text: "Kubernetes", category: "nice_to_have", dimension: "skill" },
      ],
      needs_confirmation: [],
      creation_method: "ai_generated",
    });
    createJob.mockResolvedValue({ id: "job-1" });
    createJobProfile.mockResolvedValue({ id: "profile-1" });
    startLinkedInJobImport.mockReset();
    getLinkedInJobImport.mockReset();

    uploadJobSourceFile.mockResolvedValue({
      sourceFileName: "role.pdf",
      sourceFileStatus: "ready",
      sourceFileError: "",
    });

  });

  test("imports a public LinkedIn listing into the existing editable draft flow", async () => {
    startLinkedInJobImport.mockResolvedValue({
      id: "import-1",
      source_url: "https://www.linkedin.com/jobs/view/1234567890/",
      status: "succeeded",
      result: {
        job_id: "1234567890",
        job_url: "https://www.linkedin.com/jobs/view/1234567890/",
        title: "Platform Engineer",
        company_name: "Example Co",
        location: "Remote",
        description: "Build reliable infrastructure.",
        employment_type: "Full-time",
        seniority_level: "Mid-Senior level",
        workplace_type: "Remote",
      },
    });
    renderForm();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Import from LinkedIn" }));
    await user.type(
      screen.getByLabelText("Public LinkedIn job URL"),
      "https://www.linkedin.com/jobs/view/1234567890/"
    );
    await user.click(screen.getByRole("button", { name: "Import job" }));

    await waitFor(() => expect(screen.getByLabelText(/Job Title/)).toHaveValue("Platform Engineer"));
    expect(screen.getByLabelText(/Description/)).toHaveValue("Build reliable infrastructure.");
    expect(screen.getByLabelText("Source company")).toHaveValue("Example Co");
    expect(screen.getByLabelText("Source seniority")).toHaveValue("Mid-Senior level");

    await user.click(screen.getByLabelText(/I reviewed these source details/));
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(createJob).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Platform Engineer", status: "draft" }),
      "import-1"
    ));
    expect(createJobProfile).toHaveBeenCalledWith("job-1", expect.objectContaining({
      status: "draft",
      source_metadata: expect.objectContaining({
        source_type: "linkedin",
        source_import_id: "import-1",
        company_name: "Example Co",
        seniority_level: "Mid-Senior level",
      }),
    }));
  });

  test("keeps long imported listings intact without exceeding the profile summary contract", async () => {
    const longDescription = "Public listing details. ".repeat(250);
    startLinkedInJobImport.mockResolvedValue({
      id: "import-long",
      source_url: "https://www.linkedin.com/jobs/view/1234567890/",
      status: "succeeded",
      result: {
        job_id: "1234567890",
        job_url: "https://www.linkedin.com/jobs/view/1234567890/",
        title: "Platform Engineer",
        company_name: "Example Co",
        location: "Remote",
        description: longDescription,
      },
    });
    renderForm();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Import from LinkedIn" }));
    await user.type(
      screen.getByLabelText("Public LinkedIn job URL"),
      "https://www.linkedin.com/jobs/view/1234567890/"
    );
    await user.click(screen.getByRole("button", { name: "Import job" }));

    await waitFor(() => expect(screen.getByLabelText(/Job Title/)).toHaveValue("Platform Engineer"));
    expect(screen.getByLabelText(/Description/)).toHaveValue(longDescription);
    expect(screen.getByLabelText("Job overview")).toHaveValue("");
    expect(screen.getByText(/Add a concise overview/)).toBeInTheDocument();

    await user.click(screen.getByLabelText(/I reviewed these source details/));
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(createJobProfile).toHaveBeenCalledWith("job-1", expect.objectContaining({
      profile_data: expect.objectContaining({ summary: "" }),
      source_original_listing_text: longDescription,
    })));
  });

  test("keeps manual paste available when LinkedIn import is unavailable", async () => {
    startLinkedInJobImport.mockRejectedValue({ response: { data: { detail: "Import disabled" } } });
    renderForm();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Import from LinkedIn" }));
    await user.type(
      screen.getByLabelText("Public LinkedIn job URL"),
      "https://www.linkedin.com/jobs/view/1234567890/"
    );
    await user.click(screen.getByRole("button", { name: "Import job" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Import disabled");

    await user.click(screen.getByRole("button", { name: "Paste existing description" }));
    expect(screen.getByLabelText("Existing description")).toBeInTheDocument();
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

    await waitFor(() => expect(extractJobProfile).toHaveBeenCalledWith("job-abc", expect.any(String)));
    await waitFor(() =>
      expect(screen.getByTestId("location-path")).toHaveTextContent("/jobs/job-abc")
    );
  });

  test("stores manually authored descriptions with the API's HR-created provenance value", async () => {
    createJob.mockResolvedValue({ id: "job-manual" });
    createJobProfile.mockResolvedValue({ id: "profile-manual", status: "draft" });
    renderForm();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Job Title/), "Backend Engineer");
    await user.type(screen.getByLabelText(/Description/), "Build reliable services.");
    await user.click(screen.getByRole("button", { name: "Review fields as a structured profile" }));
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(createJobProfile).toHaveBeenCalledWith("job-manual", expect.objectContaining({
      source: "hr_created",
      creation_method: "manually_created",
      raw_input_snapshot: expect.objectContaining({ creation_method: "manually_created" }),
    })));
  });

  test("AI draft keeps required and preferred skills distinct and saves an unapproved profile", async () => {
    createJob.mockResolvedValue({ id: "job-ai" });
    createJobProfile.mockResolvedValue({ id: "profile-ai", status: "draft" });
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Job Title/), "Backend Engineer");
    await user.type(screen.getByLabelText(/Department/), "Engineering");
    await user.click(screen.getByRole("button", { name: "Generate with AI" }));
    await user.click(screen.getByRole("button", { name: "Generate draft with HERA" }));
    expect(await screen.findByLabelText("Job overview")).toHaveValue("Build reliable backend services.");
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(createJobProfile).toHaveBeenCalledWith("job-ai", expect.objectContaining({
      status: "draft",
      source: "ai_extracted",
      creation_method: "ai_generated",
    })));
    const savedProfile = createJobProfile.mock.calls[0][1].profile_data;
    expect(savedProfile.requirements.map((item) => item.category)).toEqual(["must_have", "nice_to_have"]);
    expect(screen.getByTestId("location-path")).toHaveTextContent("/jobs/job-ai");
  });

  test("pasted descriptions are sent as source text and preserved on the draft", async () => {
    createJob.mockResolvedValue({ id: "job-pasted" });
    createJobProfile.mockResolvedValue({ id: "profile-pasted", status: "draft" });
    buildJobDescription.mockResolvedValueOnce({
      schema_version: "1.1",
      title: "Backend Engineer",
      summary: "Build backend systems.",
      requirements: [{
        text: "Preferred: Kubernetes", category: "nice_to_have", dimension: "skill",
        source: "manual_description", source_quote: "Preferred: Kubernetes",
      }],
      needs_confirmation: [],
      creation_method: "pasted_external",
    });
    renderForm();
    const user = userEvent.setup();
    const source = "Backend Engineer\nPreferred: Kubernetes";

    await user.click(screen.getByRole("button", { name: "Paste existing description" }));
    await user.type(screen.getByLabelText("Existing description"), source);
    await user.click(screen.getByRole("button", { name: "Structure pasted description" }));
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(buildJobDescription).toHaveBeenCalledWith(expect.objectContaining({
      operation: "parse", source_text: source,
    })));
    await waitFor(() => expect(createJobProfile).toHaveBeenCalledWith("job-pasted", expect.objectContaining({
      creation_method: "pasted_external", source_original_text: source,
    })));
  });

  test("groups the draft into responsibilities, qualifications, and skills and improves a selected item", async () => {
    buildJobDescription
      .mockResolvedValueOnce({
        schema_version: "1.4",
        title: "Backend Engineer",
        summary: "Build backend services.",
        requirements: [
          { text: "Own service reliability", category: "must_have", dimension: "responsibility" },
          { text: "Five years of experience", category: "important", dimension: "experience" },
          { text: "Python", category: "nice_to_have", dimension: "technical_skill" },
        ],
        needs_confirmation: [],
        creation_method: "ai_generated",
      })
      .mockResolvedValueOnce({
        schema_version: "1.4",
        title: "Backend Engineer",
        summary: "Lead service reliability and incident response.",
        requirements: [],
        needs_confirmation: [],
        creation_method: "ai_generated",
      });
    renderForm();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Job Title/), "Backend Engineer");
    await user.type(screen.getByLabelText(/Department/), "Engineering");
    await user.click(screen.getByRole("button", { name: "Generate with AI" }));
    await user.click(screen.getByRole("button", { name: "Generate draft with HERA" }));

    expect(await screen.findByRole("region", { name: "Responsibilities" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Qualifications" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Skills" })).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Improve with AI" })[0]);

    expect(await screen.findByText("Lead service reliability and incident response.")).toBeInTheDocument();
    expect(buildJobDescription).toHaveBeenLastCalledWith(expect.objectContaining({
      operation: "improve",
      section_name: "Responsibilities item",
      selected_section: "Own service reliability",
    }));
    await user.click(screen.getByRole("button", { name: "Use suggestion" }));
    expect(screen.getByLabelText("Responsibility")).toHaveValue("Lead service reliability and incident response.");
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
        "workMode",
      ].sort()
    );
    expect(payload).not.toHaveProperty("confidence");
    expect(payload).not.toHaveProperty("score");
    expect(payload).not.toHaveProperty("match_percent");
  });


  test("saves a selected source file with the organization-scoped draft", async () => {
    createJob.mockResolvedValue({ id: "job-file" });
    renderForm();
    const user = userEvent.setup();
    const file = new File(["job text"], "role.pdf", { type: "application/pdf" });

    await user.type(screen.getByLabelText(/Job Title/), "Backend Engineer");
    await user.upload(screen.getByLabelText(/Job description file/i), file);
    await user.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(uploadJobSourceFile).toHaveBeenCalledWith("job-file", file));
    expect(await screen.findByText(/Job saved as a draft/i)).toBeInTheDocument();

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
    await waitFor(() => expect(extractJobProfile).toHaveBeenCalledWith("job-1", expect.any(String)));
    await waitFor(() =>
      expect(screen.getByTestId("location-path")).toHaveTextContent("/jobs/job-1")
    );
  });
});

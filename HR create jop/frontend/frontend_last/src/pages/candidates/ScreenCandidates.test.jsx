import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ScreenCandidates from "./ScreenCandidates";
import {
  MAX_SINGLE_FILE_BYTES,
  ACCEPTED_EXTENSIONS,
  formatFileSize,
  getFileFingerprint,
  validateFile,
} from "./screenCandidateUtils";
import * as jobService from "../../services/jobService";
import * as screeningBatchService from "../../services/screeningBatchService";

vi.mock("../../services/jobService", () => ({
  getJobs: vi.fn(),
}));

vi.mock("../../services/screeningBatchService", () => ({
  createScreeningBatch: vi.fn(),
  getScreeningBatch: vi.fn(),
  retryBatchItem: vi.fn(),
  getJobBatches: vi.fn().mockResolvedValue([]),
}));

vi.mock("../../services/candidateService", () => ({
  createScreeningBatch: vi.fn(),
  getScreeningBatch: vi.fn(),
  retryBatchItem: vi.fn(),
}));

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location-display">{location.pathname + location.search}</div>;
}

const mockJobs = [
  {
    id: "job-1",
    title: "Senior Full Stack Engineer",
    status: "active",
    department: "Engineering",
    location: "Riyadh, KSA",
    type: "Full-time",
    description: "Build robust web applications and APIs.",
    requirements: ["5+ years React & Node.js", "Experience with PostgreSQL"],
    requiredSkills: ["React", "Node.js", "TypeScript"],
  },
  {
    id: "job-2",
    title: "Product Designer",
    status: "active",
    department: "Design",
    location: "Remote",
    type: "Full-time",
    description: "Design user-centered interfaces.",
    requirements: [],
    requiredSkills: [],
  },
];

describe("UI-07: Helper Functions and Constants", () => {
  it("defines explicit UI constants consistent with backend defaults", () => {
    expect(MAX_SINGLE_FILE_BYTES).toBe(5 * 1024 * 1024);
    expect(ACCEPTED_EXTENSIONS).toEqual([".pdf", ".docx"]);
  });

  it("formats file sizes cleanly for human readability", () => {
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1024)).toBe("1.0 KB");
    expect(formatFileSize(2048)).toBe("2.0 KB");
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5.00 MB");
    expect(formatFileSize(null)).toBe("0 B");
  });

  it("generates deterministic local fingerprints for duplicate detection", () => {
    const file = { name: "cv.pdf", size: 1024, lastModified: 1700000000 };
    expect(getFileFingerprint(file)).toBe("cv.pdf:1024:1700000000");
  });

  it("validates file format correctly", () => {
    const validPdf = { name: "resume.pdf", size: 50000, lastModified: 1 };
    const validDocx = { name: "resume.docx", size: 50000, lastModified: 1 };
    const invalidTxt = { name: "notes.txt", size: 50000, lastModified: 1 };

    expect(validateFile(validPdf).valid).toBe(true);
    expect(validateFile(validDocx).valid).toBe(true);

    const txtResult = validateFile(invalidTxt);
    expect(txtResult.valid).toBe(false);
    expect(txtResult.code).toBe("unsupported_type");
    expect(txtResult.reason).toContain("only PDF and DOCX");
  });

  it("validates file size limit strictly against MAX_SINGLE_FILE_BYTES (5 MB)", () => {
    const normalFile = { name: "resume.pdf", size: 4 * 1024 * 1024, lastModified: 1 };
    const oversizedFile = { name: "large_resume.pdf", size: 6 * 1024 * 1024, lastModified: 1 };

    expect(validateFile(normalFile).valid).toBe(true);

    const oversizedResult = validateFile(oversizedFile);
    expect(oversizedResult.valid).toBe(false);
    expect(oversizedResult.code).toBe("size_limit");
    expect(oversizedResult.reason).toContain("exceeds the 5 MB maximum size limit");
  });

  it("flags duplicate selection as an advisory local client hint", () => {
    const file = { name: "resume.pdf", size: 50000, lastModified: 12345 };
    const existing = new Set(["resume.pdf:50000:12345"]);

    const dupResult = validateFile(file, existing);
    expect(dupResult.valid).toBe(false);
    expect(dupResult.code).toBe("duplicate_hint");
    expect(dupResult.reason).toContain("Duplicate file already selected");
    expect(dupResult.reason).toContain("local client hint");
  });
});

describe("UI-07: Job Selection & Truthful Criteria Summary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    jobService.getJobs.mockResolvedValue(mockJobs);
  });

  it("renders selected job details and displays truthful criteria without fabricating weights or approval states", async () => {
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    expect(screen.getByText("5+ years React & Node.js")).toBeInTheDocument();
    expect(screen.getByText("Experience with PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("TypeScript")).toBeInTheDocument();

    // Truthful notice present
    expect(
      screen.getByText(/Truthful criteria notice: Loaded directly from the job record/i)
    ).toBeInTheDocument();

    // Verify NO fabricated weights or percentages exist in criteria
    expect(screen.queryByText(/\bweight:\s*\d+/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Approved by HR/i)).not.toBeInTheDocument();
  });

  it("renders truthful message when selected job has no explicit criteria", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    const select = screen.getByLabelText(/Job/i);

    // Switch to Product Designer which has empty requirements & skills
    await user.selectOptions(select, "job-2");

    expect(await screen.findByText(/No explicit criteria or skills configured on this job/i)).toBeInTheDocument();
  });
});

describe("UI-07: File Selection, Pre-Submission Validation & Removal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    jobService.getJobs.mockResolvedValue(mockJobs);
  });

  it("never silently discards unsupported files: displays valid and rejected lists separately", async () => {
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    const input = screen.getByLabelText(/Upload candidate CV files/i);

    const validFile = new File(["valid content"], "candidate_alice.pdf", {
      type: "application/pdf",
      lastModified: 1000,
    });
    const invalidFile = new File(["some text"], "candidate_notes.txt", {
      type: "text/plain",
      lastModified: 2000,
    });

    fireEvent.change(input, {
      target: { files: [validFile, invalidFile] },
    });

    // Valid file appears in Selected Resumes
    expect(screen.getByText("candidate_alice.pdf")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();

    // Rejected file appears in Rejected Files section with reason
    expect(screen.getByRole("alert", { name: /Rejected files/i })).toBeInTheDocument();
    expect(screen.getByText("candidate_notes.txt")).toBeInTheDocument();
    expect(screen.getByText("Invalid")).toBeInTheDocument();
    expect(
      screen.getByText(/Unsupported file format \(only PDF and DOCX files are supported\)/i)
    ).toBeInTheDocument();
  });

  it("displays clear error when a file exceeds the 5 MB limit", async () => {
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    const input = screen.getByLabelText(/Upload candidate CV files/i);

    // Create a 6 MB mock file
    const oversizedFile = new File(["x"], "huge_portfolio.pdf", {
      type: "application/pdf",
      lastModified: 3000,
    });
    Object.defineProperty(oversizedFile, "size", { value: 6 * 1024 * 1024 });

    fireEvent.change(input, {
      target: { files: [oversizedFile] },
    });

    expect(screen.getByText("huge_portfolio.pdf")).toBeInTheDocument();
    expect(
      screen.getByText(/File exceeds the 5 MB maximum size limit \(6.00 MB\)/i)
    ).toBeInTheDocument();
  });

  it("detects duplicate selection hint using browser-safe fingerprint", async () => {
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    const input = screen.getByLabelText(/Upload candidate CV files/i);

    const file1 = new File(["content"], "candidate_bob.pdf", {
      type: "application/pdf",
      lastModified: 4000,
    });
    Object.defineProperty(file1, "size", { value: 2048 });

    const file2 = new File(["content"], "candidate_bob.pdf", {
      type: "application/pdf",
      lastModified: 4000,
    });
    Object.defineProperty(file2, "size", { value: 2048 });

    // Select file1
    fireEvent.change(input, {
      target: { files: [file1] },
    });
    expect(screen.getByText("candidate_bob.pdf")).toBeInTheDocument();

    // Attempt to select identical file2
    fireEvent.change(input, {
      target: { files: [file2] },
    });

    // Second file appears in rejected list as duplicate selection hint
    expect(
      screen.getByText(/Duplicate file already selected \(local client hint: matching name, size, and modified date/i)
    ).toBeInTheDocument();
  });

  it("provides accessible type='button' removal controls for both valid and rejected files", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    const input = screen.getByLabelText(/Upload candidate CV files/i);

    const validFile = new File(["valid"], "charlie.pdf", {
      type: "application/pdf",
      lastModified: 5000,
    });
    const invalidFile = new File(["invalid"], "bad.png", {
      type: "image/png",
      lastModified: 6000,
    });

    fireEvent.change(input, {
      target: { files: [validFile, invalidFile] },
    });

    // Remove valid file
    const removeValidBtn = screen.getByRole("button", { name: "Remove charlie.pdf" });
    expect(removeValidBtn).toHaveAttribute("type", "button");
    await user.click(removeValidBtn);
    expect(screen.queryByText("charlie.pdf")).not.toBeInTheDocument();

    // Dismiss rejected file
    const dismissRejectedBtn = screen.getByRole("button", {
      name: "Dismiss rejected file bad.png",
    });
    expect(dismissRejectedBtn).toHaveAttribute("type", "button");
    await user.click(dismissRejectedBtn);
    expect(screen.queryByText("bad.png")).not.toBeInTheDocument();
  });

  it("clears all rejected items with the clear rejected list button", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    const input = screen.getByLabelText(/Upload candidate CV files/i);

    const bad1 = new File(["1"], "file1.png", { type: "image/png" });
    const bad2 = new File(["2"], "file2.txt", { type: "text/plain" });

    fireEvent.change(input, {
      target: { files: [bad1, bad2] },
    });

    expect(screen.getByText("file1.png")).toBeInTheDocument();
    expect(screen.getByText("file2.txt")).toBeInTheDocument();

    const clearBtn = screen.getByRole("button", { name: /Clear rejected list/i });
    expect(clearBtn).toHaveAttribute("type", "button");
    await user.click(clearBtn);

    expect(screen.queryByText("file1.png")).not.toBeInTheDocument();
    expect(screen.queryByText("file2.txt")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert", { name: /Rejected files/i })).not.toBeInTheDocument();
  });
});

describe("UI-07: Submission Progress & Real API Rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    jobService.getJobs.mockResolvedValue(mockJobs);
  });

  it("explains submission is in progress without simulating fake per-file progress", async () => {
    const user = userEvent.setup();
    let resolveBatch;
    screeningBatchService.createScreeningBatch.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveBatch = resolve;
        })
    );

    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    const input = screen.getByLabelText(/Upload candidate CV files/i);

    const validFile = new File(["valid"], "dave.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      lastModified: 7000,
    });

    fireEvent.change(input, {
      target: { files: [validFile] },
    });

    const submitBtn = screen.getByRole("button", { name: /Start Batch Screening/i });
    await user.click(submitBtn);

    // In-progress explanation banner
    const banner = screen.getByRole("status");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/Submission in progress/i);
    expect(banner).toHaveTextContent(/Uploading 1 resume\(s\) to server and creating screening batch/i);

    // Button shows Submitting
    expect(submitBtn).toBeDisabled();
    expect(submitBtn).toHaveTextContent(/Submitting batch/i);

    // Resolve API call
    resolveBatch({
      batch_id: "batch-101",
      job_id: "job-1",
      status: "running",
      total_items: 1,
      queued_items: 0,
      running_items: 1,
      done_items: 0,
      failed_items: 0,
      duplicate_items: 0,
      items: [
        {
          id: "item-1",
          original_filename: "dave.docx",
          file_size: 15360,
          status: "running",
          score: null,
        },
      ],
    });

    await waitFor(() => {
      expect(screen.getByText("batch-101")).toBeInTheDocument();
    });

    // Renders original filename from real API response field
    expect(screen.getByText("dave.docx")).toBeInTheDocument();
    // Real API un-scored item renders —
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("handles synchronous submission errors honestly from API response", async () => {
    const user = userEvent.setup();
    screeningBatchService.createScreeningBatch.mockRejectedValue({
      response: {
        status: 400,
        data: { detail: "Backend storage quota exceeded for organization." },
      },
    });

    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    const input = screen.getByLabelText(/Upload candidate CV files/i);

    const validFile = new File(["valid"], "elena.pdf", {
      type: "application/pdf",
      lastModified: 8000,
    });

    fireEvent.change(input, {
      target: { files: [validFile] },
    });

    const submitBtn = screen.getByRole("button", { name: /Start Batch Screening/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Backend storage quota exceeded for organization.")
      ).toBeInTheDocument();
    });
  });
});

describe("Screening setup loading and empty states", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    jobService.getJobs.mockResolvedValue(mockJobs);
    screeningBatchService.getJobBatches.mockResolvedValue([]);
  });

  it("explains when there are no jobs and links to the supported job creation flow", async () => {
    jobService.getJobs.mockResolvedValueOnce([]);
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    expect(await screen.findByText(/No jobs available for screening yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Create a job/i })).toHaveAttribute("href", "/jobs/new");
    expect(screen.getByRole("button", { name: /Start Batch Screening/i })).toBeDisabled();
  });

  it("offers a retry after jobs fail to load", async () => {
    const user = userEvent.setup();
    jobService.getJobs
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(mockJobs);
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Couldn't load your jobs from the backend/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Try again/i }));
    expect(await screen.findByText("Senior Full Stack Engineer")).toBeInTheDocument();
    expect(jobService.getJobs).toHaveBeenCalledTimes(2);
  });

  it("shows an honest empty message when the job has no prior screening batches", async () => {
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    expect(await screen.findByText(/No screening batches for this job yet/i)).toBeInTheDocument();
    expect(screen.getByText(/After you submit CVs, their processing status will appear here/i)).toBeInTheDocument();
  });

  it("distinguishes batch history request failure from an empty history and allows retry", async () => {
    const user = userEvent.setup();
    screeningBatchService.getJobBatches
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([]);
    render(
      <MemoryRouter>
        <ScreenCandidates />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Couldn't load recent screening batches/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Try again/i }));
    expect(await screen.findByText(/No screening batches for this job yet/i)).toBeInTheDocument();
  });

  it("reopens a completed batch while a previous batch request is still in flight", async () => {
    const user = userEvent.setup();
    const completedBatch = {
      id: "batch-completed",
      batch_id: "batch-completed",
      job_id: "job-1",
      status: "completed",
      total_files: 1,
      total_items: 1,
      counts: { total: 1, queued: 0, running: 0, completed: 1, failed: 0 },
      queued_items: 0,
      running_items: 0,
      done_items: 1,
      failed_items: 0,
      items: [
        {
          id: "item-completed",
          original_filename: "synthetic_completed.pdf",
          status: "done",
          score: 88,
          application_id: "app-completed",
        },
      ],
    };
    screeningBatchService.getJobBatches.mockResolvedValue([
      { id: "batch-running", status: "running", total_files: 1, counts: { completed: 0 } },
      { id: "batch-completed", status: "completed", total_files: 1, counts: { completed: 1 } },
    ]);

    let resolvePreviousBatch;
    screeningBatchService.getScreeningBatch.mockImplementation((batchId) => {
      if (batchId === "batch-running") {
        return new Promise((resolve) => {
          resolvePreviousBatch = resolve;
        });
      }
      return Promise.resolve(completedBatch);
    });

    render(
      <MemoryRouter initialEntries={["/candidates/screen"]}>
        <Routes>
          <Route
            path="/candidates/screen"
            element={
              <>
                <ScreenCandidates />
                <LocationDisplay />
              </>
            }
          />
          <Route path="/applications/:applicationId/review" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText("Senior Full Stack Engineer");
    await screen.findByText("Recent screening batches");
    const initialViewButton = screen.getAllByRole("button", { name: "View" })[0];
    await user.click(initialViewButton);
    await waitFor(() => {
      expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledWith("batch-running");
    });
    expect(
      screen.getByText("Connecting to screening batch batch-running...")
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "View" }));

    expect(await screen.findByText("COMPLETED")).toBeInTheDocument();
    expect(screen.getByText("synthetic_completed.pdf")).toBeInTheDocument();
    expect(screen.queryByText(/Connecting to screening batch/i)).not.toBeInTheDocument();
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledWith("batch-completed");

    await user.click(
      screen.getByRole("button", { name: /Review evaluation for synthetic_completed.pdf/i })
    );
    expect(screen.getByTestId("location-display")).toHaveTextContent(
      "/applications/app-completed/review"
    );

    await act(async () => {
      resolvePreviousBatch({ status: "running", items: [] });
    });
  });
});

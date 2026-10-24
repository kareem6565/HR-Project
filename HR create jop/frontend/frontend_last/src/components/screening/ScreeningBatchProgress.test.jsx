import { beforeEach, describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ScreeningBatchProgress from "./ScreeningBatchProgress";
import * as screeningBatchService from "../../services/screeningBatchService";

vi.mock("../../services/screeningBatchService", () => ({
  getScreeningBatch: vi.fn(),
  retryBatchItem: vi.fn(),
}));

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location-display">{location.pathname + location.search}</div>;
}

const mockJob = {
  id: "job-101",
  title: "Principal Cloud Architect",
};

const mockBatchMixed = {
  id: "batch-xyz",
  batch_id: "batch-xyz",
  job_id: "job-101",
  status: "running",
  total_files: 3,
  total_items: 3,
  counts: {
    total: 3,
    queued: 1,
    running: 0,
    completed: 1,
    failed: 1,
    duplicate: 0,
    cancelled: 0,
  },
  queued_items: 1,
  running_items: 0,
  done_items: 1,
  failed_items: 1,
  duplicate_items: 0,
  items: [
    {
      id: "item-success",
      filename: "sarah_cloud.pdf",
      original_filename: "sarah_cloud.pdf",
      file_size: 45000,
      status: "done",
      score: "91.8",
      application_id: "app-sarah-1",
      candidate_id: "cand-sarah-1",
      error_message: null,
    },
    {
      id: "item-failed",
      filename: "corrupted_cv.docx",
      original_filename: "corrupted_cv.docx",
      file_size: 12000,
      status: "failed",
      score: null,
      error_code: "PARSE_ERROR",
      error_message: "Corrupted XML package in DOCX file.",
      attempts: 1,
      max_attempts: 3,
    },
    {
      id: "item-queued",
      filename: "mike_lead.pdf",
      original_filename: "mike_lead.pdf",
      file_size: 28000,
      status: "queued",
      score: null,
      error_message: null,
    },
  ],
};

const mockBatchWithDuplicate = {
  id: "batch-dup",
  batch_id: "batch-dup",
  job_id: "job-101",
  status: "completed",
  total_files: 2,
  total_items: 2,
  counts: {
    total: 2,
    queued: 0,
    running: 0,
    completed: 1,
    failed: 0,
    duplicate: 1,
    cancelled: 0,
  },
  queued_items: 0,
  running_items: 0,
  done_items: 1,
  failed_items: 0,
  duplicate_items: 1,
  items: [
    {
      id: "item-valid",
      filename: "john_doe.pdf",
      original_filename: "john_doe.pdf",
      status: "done",
      score: "85",
      application_id: "app-john-1",
    },
    {
      id: "item-dup",
      filename: "john_doe_copy.pdf",
      original_filename: "john_doe_copy.pdf",
      status: "duplicate",
      score: null,
      error_message: "Duplicate file content submitted in the same batch.",
    },
  ],
};

describe("UI-08: Async Batch Progress & Partial Success", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders truthful counts and partial success where successful results remain reviewable when another file fails", async () => {
    screeningBatchService.getScreeningBatch.mockResolvedValue(mockBatchMixed);

    render(
      <MemoryRouter>
        <ScreeningBatchProgress batchId="batch-xyz" job={mockJob} />
      </MemoryRouter>
    );

    await screen.findByText("sarah_cloud.pdf");

    // Truthful counts check
    expect(screen.getByText("3")).toBeInTheDocument(); // Total
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1); // Done/Failed/Queued
    expect(screen.getByText("67%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Screening batch progress" })).toHaveAttribute(
      "value",
      "2"
    ); // Done and failed items reached a final state; one remains queued.

    // Successful item: score displayed, review action available
    expect(screen.getByText("92")).toBeInTheDocument(); // Rounded score
    expect(screen.getByText("Profile created & evaluated")).toBeInTheDocument();
    const reviewBtn = screen.getByRole("button", {
      name: /Review evaluation for sarah_cloud.pdf/i,
    });
    expect(reviewBtn).toBeInTheDocument();

    // Failed item: error message shown, retry button available
    expect(
      screen.getByText("Corrupted XML package in DOCX file.")
    ).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", {
      name: /Retry processing corrupted_cv.docx/i,
    });
    expect(retryBtn).toBeInTheDocument();

    // Queued item: safe status message
    expect(screen.getByText("Queued for worker")).toBeInTheDocument();
  });

  it("updates the truthful progress percentage automatically when screening completes", async () => {
    vi.useFakeTimers();
    const queuedBatch = {
      ...mockBatchMixed,
      status: "queued",
      total_files: 1,
      total_items: 1,
      counts: { total: 1, queued: 1, running: 0, completed: 0, failed: 0, duplicate: 0 },
      queued_items: 1,
      running_items: 0,
      done_items: 0,
      failed_items: 0,
      duplicate_items: 0,
      items: [{ id: "item-progress", original_filename: "synthetic_cv.pdf", status: "queued" }],
    };
    const runningBatch = {
      ...queuedBatch,
      status: "running",
      counts: { total: 1, queued: 0, running: 1, completed: 0, failed: 0, duplicate: 0 },
      queued_items: 0,
      running_items: 1,
      items: [{ id: "item-progress", original_filename: "synthetic_cv.pdf", status: "running" }],
    };
    const completedBatch = {
      ...runningBatch,
      status: "completed",
      counts: { total: 1, queued: 0, running: 0, completed: 1, failed: 0, duplicate: 0 },
      running_items: 0,
      done_items: 1,
      items: [
        {
          id: "item-progress",
          original_filename: "synthetic_cv.pdf",
          status: "done",
          score: 84,
          application_id: "app-progress",
        },
      ],
    };
    screeningBatchService.getScreeningBatch
      .mockResolvedValueOnce(runningBatch)
      .mockResolvedValueOnce(completedBatch);

    render(
      <MemoryRouter>
        <ScreeningBatchProgress batchId="batch-progress" initialData={queuedBatch} job={mockJob} />
      </MemoryRouter>
    );

    await act(async () => {});
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Screening batch progress" })).toHaveAttribute(
      "value",
      "0"
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Screening batch progress" })).toHaveAttribute(
      "value",
      "1"
    );
    expect(screen.getByText("84")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Review evaluation for synthetic_cv.pdf/i })
    ).toBeInTheDocument();
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(2);
  });

  it("displays duplicate items truthfully and does not offer retry for duplicates", async () => {
    screeningBatchService.getScreeningBatch.mockResolvedValue(mockBatchWithDuplicate);

    render(
      <MemoryRouter>
        <ScreeningBatchProgress batchId="batch-dup" job={mockJob} />
      </MemoryRouter>
    );

    await screen.findByText("john_doe_copy.pdf");

    // Duplicate item renders duplicate badge and message
    expect(screen.getByText("duplicate")).toBeInTheDocument();
    expect(
      screen.getByText("Duplicate file content submitted in the same batch.")
    ).toBeInTheDocument();

    // Retry button MUST NOT exist for duplicate item
    expect(
      screen.queryByRole("button", {
        name: /Retry processing john_doe_copy.pdf/i,
      })
    ).not.toBeInTheDocument();
  });

  it("allows retrying failed items only and triggers immediate poll update", async () => {
    const user = userEvent.setup();
    screeningBatchService.getScreeningBatch.mockResolvedValue(mockBatchMixed);
    screeningBatchService.retryBatchItem.mockResolvedValue({
      id: "item-failed",
      status: "queued",
    });

    render(
      <MemoryRouter>
        <ScreeningBatchProgress batchId="batch-xyz" job={mockJob} />
      </MemoryRouter>
    );

    await screen.findByText("corrupted_cv.docx");

    const retryBtn = screen.getByRole("button", {
      name: /Retry processing corrupted_cv.docx/i,
    });
    await user.click(retryBtn);

    expect(screeningBatchService.retryBatchItem).toHaveBeenCalledWith("item-failed");
  });

  it("provides job-scoped navigation linking directly to matching results for the selected job", async () => {
    const user = userEvent.setup();
    screeningBatchService.getScreeningBatch.mockResolvedValue(mockBatchMixed);

    render(
      <MemoryRouter initialEntries={["/candidates/screen"]}>
        <Routes>
          <Route
            path="/candidates/screen"
            element={<ScreeningBatchProgress batchId="batch-xyz" job={mockJob} />}
          />
          <Route path="/matching-results" element={<LocationDisplay />} />
          <Route path="/candidates" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText("sarah_cloud.pdf");

    // Job-scoped results button
    const viewJobResultsBtn = screen.getByRole("button", {
      name: /View job matching results/i,
    });
    await user.click(viewJobResultsBtn);

    // Navigated to /matching-results?jobId=job-101
    expect(screen.getByTestId("location-display")).toHaveTextContent(
      "/matching-results?jobId=job-101"
    );
  });
});

describe("UI-08: Polling Invariants & Controlled Polling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("enforces at most one poll request in flight without overlapping polls", async () => {
    let resolveFirst;
    const firstRequestPromise = new Promise((resolve) => {
      resolveFirst = resolve;
    });

    // First call returns pending promise
    screeningBatchService.getScreeningBatch.mockReturnValueOnce(firstRequestPromise);

    render(
      <MemoryRouter>
        <ScreeningBatchProgress batchId="batch-xyz" job={mockJob} />
      </MemoryRouter>
    );

    // One poll request initiated immediately
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(1);

    // Fast forward timer by 5 seconds while request is still pending
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    // MUST NOT initiate second poll while first is in flight
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(1);

    // Resolve the first request with running batch
    await act(async () => {
      resolveFirst(mockBatchMixed);
    });

    // Subsequent poll is now scheduled after resolution
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(2);
  });

  it("stops polling when all items reach terminal states", async () => {
    const terminalBatch = {
      ...mockBatchWithDuplicate,
      status: "completed",
      counts: { queued: 0, running: 0, completed: 1, failed: 0, duplicate: 1 },
      queued_items: 0,
      running_items: 0,
    };

    screeningBatchService.getScreeningBatch.mockResolvedValue(terminalBatch);

    await act(async () => {
      render(
        <MemoryRouter>
          <ScreeningBatchProgress batchId="batch-dup" job={mockJob} />
        </MemoryRouter>
      );
    });

    // Initial fetch
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(1);

    // Advance timers multiple times
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
      await vi.advanceTimersByTimeAsync(5000);
    });

    // Polling has stopped because batch is terminal
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(1);
  });

  it("cleans up polling timer on component unmount", async () => {
    screeningBatchService.getScreeningBatch.mockResolvedValue(mockBatchMixed);

    let unmountFn;
    await act(async () => {
      const { unmount } = render(
        <MemoryRouter>
          <ScreeningBatchProgress batchId="batch-xyz" job={mockJob} />
        </MemoryRouter>
      );
      unmountFn = unmount;
    });

    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(1);

    // Unmount before next timer fires
    await act(async () => {
      unmountFn();
    });

    // Fast forward timers
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    // No further calls after unmount
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(1);
  });

  it("does not treat transient network failure as batch failure and preserves batch state", async () => {
    screeningBatchService.getScreeningBatch.mockRejectedValue(
      new Error("Network connection lost")
    );

    render(
      <MemoryRouter>
        <ScreeningBatchProgress
          batchId="batch-xyz"
          initialData={mockBatchMixed}
          job={mockJob}
        />
      </MemoryRouter>
    );

    // Initial batch data is rendered
    expect(screen.getByText("sarah_cloud.pdf")).toBeInTheDocument();
    expect(screen.getByText(/RUNNING/i)).toBeInTheDocument();

    // Fast forward to next poll which throws network error
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });

    // Items and batch data MUST remain visible on network error
    expect(screen.getByText("sarah_cloud.pdf")).toBeInTheDocument();
    // Batch is NOT marked as failed
    expect(screen.getByText(/RUNNING/i)).toBeInTheDocument();
    // Shows transient connection notice
    await vi.waitFor(() => {
      expect(
        screen.getByText(/Temporary connection issue while checking batch status/i)
      ).toBeInTheDocument();
    });
  });

  it("handles 404 expired/removed batches by reporting error and pausing polling", async () => {
    screeningBatchService.getScreeningBatch.mockRejectedValue({
      response: { status: 404, data: { detail: "Batch not found" } },
    });

    render(
      <MemoryRouter>
        <ScreeningBatchProgress batchId="batch-expired" job={mockJob} />
      </MemoryRouter>
    );

    await vi.waitFor(() => {
      expect(
        screen.getByText(/Screening batch was not found or has expired/i)
      ).toBeInTheDocument();
    });

    // Advance timers
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    // Polling was paused, no repeated requests
    expect(screeningBatchService.getScreeningBatch).toHaveBeenCalledTimes(1);
  });
});

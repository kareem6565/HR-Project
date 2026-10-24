import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import MatchingResults from "./MatchingResults";
import { getJobs } from "../../services/jobService";
import { getRanking, recordPipelineDecision } from "../../services/matchingService";
import { getReviewBundle } from "../../services/reviewService";

// Fidelity contract for Matching Results (UI-04):
//   - Candidate ranking is scoped strictly to one selected job.
//     When no job is selected, a job picker is presented; candidates from
//     different jobs are never combined into a single ranking.
//   - Scores, statuses, groups, and evidence are backend-derived values
//     displayed unchanged; nothing is computed or fabricated client-side.
//   - Quick decision actions do NOT execute silently on click; they open a
//     confirmation modal with candidate details, action label, and optional reason.
//   - Low-priority candidates are kept visible and reviewable in a collapsible section.
//   - All filters (jobId, search, status, group, minScore) are URL-persisted.

vi.mock("../../services/matchingService", () => ({
  getRanking: vi.fn(),
  recordPipelineDecision: vi.fn(),
}));

vi.mock("../../services/jobService", () => ({
  getJobs: vi.fn(),
}));

vi.mock("../../services/reviewService", () => ({
  getReviewBundle: vi.fn(),
}));

const ADVANCE_ROW = {
  id: "app-1",
  applicationId: "app-1",
  candidateId: "c-1",
  candidateName: "Ada Lovelace",
  jobId: "j-1",
  jobTitle: "Backend Engineer",
  status: "advanced",
  score: 88,
  reviewed: true,
  group: "must_review",
  evidence: [
    { requirementKey: "python", evidenceType: "matched", text: "Python" },
    { requirementKey: "gcp", evidenceType: "partial", text: "GCP" },
    { requirementKey: "kubernetes", evidenceType: "missing", text: "Kubernetes" },
  ],
};

const HOLD_ROW = {
  id: "app-2",
  applicationId: "app-2",
  candidateId: "c-2",
  candidateName: "Grace Hopper",
  jobId: "j-1",
  jobTitle: "Backend Engineer",
  status: "hold",
  score: 60,
  reviewed: true,
  group: "consider",
  evidence: [],
};

const REJECT_ROW = {
  id: "app-3",
  applicationId: "app-3",
  candidateId: "c-3",
  candidateName: "Alan Turing",
  jobId: "j-1",
  jobTitle: "Backend Engineer",
  status: "rejected",
  score: 40,
  reviewed: true,
  group: "lower_priority",
  evidence: [{ requirementKey: "python", evidenceType: "matched", text: "Python" }],
};

const READY_ROW = {
  id: "app-4",
  applicationId: "app-4",
  candidateId: "c-4",
  candidateName: "Katherine Johnson",
  jobId: "j-1",
  jobTitle: "Backend Engineer",
  status: "ready_for_review",
  score: null,
  reviewed: false,
  group: "lower_priority",
  evidence: [],
};

const OTHER_JOB_ROW = {
  id: "app-5",
  applicationId: "app-5",
  candidateId: "c-5",
  candidateName: "Linus Pauling",
  jobId: "j-2",
  jobTitle: "Data Engineer",
  status: "hold",
  score: 75,
  reviewed: true,
  group: "must_review",
  evidence: [],
};

const jobList = [
  { id: "j-1", title: "Backend Engineer", department: "Engineering" },
  { id: "j-2", title: "Data Engineer", department: "Data" },
];

function renderPage(rows = [ADVANCE_ROW], initialEntries = ["/matching-results?jobId=j-1"]) {
  getRanking.mockResolvedValue(rows);
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <MatchingResults />
    </MemoryRouter>
  );
}

function ReviewProbe() {
  const { id } = useParams();
  return <div>REVIEW_SCREEN:{id}</div>;
}

function renderWithRoutes(rows = [ADVANCE_ROW], initialEntries = ["/matching-results?jobId=j-1"]) {
  getRanking.mockResolvedValue(rows);
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/matching-results" element={<MatchingResults />} />
        <Route path="/applications/:id/review" element={<ReviewProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("MatchingResults fidelity: real backend-derived data", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRanking.mockResolvedValue([ADVANCE_ROW]);
    recordPipelineDecision.mockResolvedValue({});
    getJobs.mockResolvedValue(jobList);
  });

  it("compares selected same-job candidates using persisted evidence and scores", async () => {
    const user = userEvent.setup();
    const secondRow = { ...HOLD_ROW, applicationId: "app-2", id: "app-2" };
    getReviewBundle
      .mockResolvedValueOnce({
        application: { id: "app-1", job_id: "j-1" },
        candidate: { name: "Ada Lovelace" },
        poolRow: { score: "88", decision: "advance" },
        evidence: [{
          evidence_type: "matched",
          requirement_ref: { requirement_key: "python", text: "Python" },
          candidate_evidence: { quote: "Built APIs in Python.", quote_verified: true },
        }],
      })
      .mockResolvedValueOnce({
        application: { id: "app-2", job_id: "j-1" },
        candidate: { name: "Grace Hopper" },
        poolRow: { score: "60", decision: "hold" },
        evidence: [{
          evidence_type: "partial",
          requirement_ref: { requirement_key: "python", text: "Python" },
          candidate_evidence: { text: "unverified candidate evidence", quote_verified: false },
        }],
      });

    renderPage([ADVANCE_ROW, secondRow]);
    await user.click(await screen.findByRole("checkbox", { name: "Select Ada Lovelace for comparison" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Grace Hopper for comparison" }));
    await user.click(screen.getByRole("button", { name: /Compare selected \(2\)/ }));

    expect(await screen.findByText("Compare candidates · Backend Engineer")).toBeInTheDocument();
    const dialog = screen.getByRole("dialog", { name: /Compare candidates/ });
    expect(within(dialog).getByText("Ada Lovelace")).toBeInTheDocument();
    expect(within(dialog).getByText("Grace Hopper")).toBeInTheDocument();
    expect(within(dialog).getByText("Score: 88%")).toBeInTheDocument();
    expect(within(dialog).getByText("Score: 60%")).toBeInTheDocument();
    expect(within(dialog).getByText(/Built APIs in Python\./)).toBeInTheDocument();
    expect(within(dialog).queryByText(/unverified candidate evidence/)).not.toBeInTheDocument();
    expect(within(dialog).getByText(/does not recalculate scores or recommend/)).toBeInTheDocument();
  });

  it("displays a concise score value in job context", async () => {
    renderPage();
    await screen.findByText("Ada Lovelace");
    expect(screen.getByText("88")).toBeTruthy();
  });

  it("renders the backend evidence chips unchanged", async () => {
    renderPage();
    await screen.findByText("Ada Lovelace");
    expect(screen.getByText("Python")).toBeTruthy();
    expect(screen.getByText("GCP")).toBeTruthy();
    expect(screen.getByText("Kubernetes")).toBeTruthy();
  });

  it("shows an honest empty evidence state instead of fabricated chips", async () => {
    renderPage([HOLD_ROW]);
    await screen.findByText("Grace Hopper");
    expect(screen.getByText("No requirement evidence in this view")).toBeTruthy();
    expect(screen.queryByText(/Python/i)).toBeNull();
    expect(screen.queryByText(/Kubernetes/i)).toBeNull();
  });

  it("renders the backend group unchanged", async () => {
    const user = userEvent.setup();
    renderPage([ADVANCE_ROW, READY_ROW]);
    await screen.findByText("Ada Lovelace");
    expect(within(screen.getByText("Must Review").closest(".recommendation")).getByText("Must Review")).toBeTruthy();

    // Katherine is in lower priority section
    const showLower = screen.getByRole("button", { name: /show lower priority/i });
    await user.click(showLower);
    expect(screen.getByText("Lower Priority")).toBeTruthy();
  });

  it("shows no group pill when a row has no group", async () => {
    renderPage([{ ...ADVANCE_ROW, group: "" }]);
    await screen.findByText("Ada Lovelace");
    expect(screen.queryByText("Must Review")).toBeNull();
    expect(screen.queryByText("Lower Priority")).toBeNull();
  });
});

describe("MatchingResults UI-04: Job Scoping & Job Picker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRanking.mockResolvedValue([ADVANCE_ROW, OTHER_JOB_ROW]);
    recordPipelineDecision.mockResolvedValue({});
    getJobs.mockResolvedValue(jobList);
  });

  it("shows a clear job picker when no job is selected and never combines unrelated jobs", async () => {
    renderPage([ADVANCE_ROW, OTHER_JOB_ROW], ["/matching-results"]);

    // Clear Job Picker displayed
    await screen.findByText("Select a Job to View Candidate Ranking");
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Data Engineer")).toBeInTheDocument();

    // Candidates from different jobs are NOT combined together
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();
    expect(screen.queryByText("Linus Pauling")).not.toBeInTheDocument();
  });

  it("scopes candidate ranking strictly to the selected job", async () => {
    renderPage([ADVANCE_ROW, OTHER_JOB_ROW], ["/matching-results?jobId=j-1"]);

    await screen.findByText("Ada Lovelace");
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();

    // Linus Pauling belongs to j-2, so must NOT be in j-1 ranking
    expect(screen.queryByText("Linus Pauling")).not.toBeInTheDocument();
  });

  it("shows rank number strictly inside selected job context", async () => {
    renderPage([ADVANCE_ROW, HOLD_ROW], ["/matching-results?jobId=j-1"]);

    await screen.findByText("Ada Lovelace");
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
  });
});

describe("MatchingResults UI-04: Low-Priority Candidate Visibility", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRanking.mockResolvedValue([ADVANCE_ROW, READY_ROW]);
    recordPipelineDecision.mockResolvedValue({});
    getJobs.mockResolvedValue(jobList);
  });

  it("keeps lower-priority candidates visible and reviewable in a collapsible section", async () => {
    const user = userEvent.setup();
    renderPage([ADVANCE_ROW, READY_ROW], ["/matching-results?jobId=j-1"]);

    await screen.findByText("Ada Lovelace");

    // Primary candidate is immediately shown
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();

    // Lower priority candidate has a clearly labelled disclosure
    const toggle = screen.getByRole("button", { name: /show lower priority candidates/i });
    expect(toggle).toBeInTheDocument();
    expect(screen.queryByText("Katherine Johnson")).not.toBeInTheDocument();

    // Expanding disclosure reveals lower priority candidates
    await user.click(toggle);
    expect(screen.getByText("Katherine Johnson")).toBeInTheDocument();
  });
});

describe("MatchingResults UI-04: Deliberate Decision Confirmation Modal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRanking.mockResolvedValue([ADVANCE_ROW]);
    recordPipelineDecision.mockResolvedValue({});
    getJobs.mockResolvedValue(jobList);
  });

  it("does NOT execute decision silently on icon click; opens confirmation dialog with reason", async () => {
    const user = userEvent.setup();
    renderPage();

    const advance = await screen.findByRole("button", { name: /advance/i });
    await user.click(advance);

    // Dialog is opened, decision not yet submitted
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Confirm Advance: Ada Lovelace/i)).toBeInTheDocument();
    expect(recordPipelineDecision).not.toHaveBeenCalled();

    // Enter optional reason
    const reasonInput = screen.getByPlaceholderText(/Enter reason for audit record/i);
    await user.type(reasonInput, "Strong distributed systems background");

    // Confirm decision
    await user.click(screen.getByRole("button", { name: "Confirm Advance" }));

    await waitFor(() => {
      expect(recordPipelineDecision).toHaveBeenCalledWith(
        "app-1",
        "advance",
        "Strong distributed systems background"
      );
    });
  });

  it("submits a hold decision via confirmation modal", async () => {
    const user = userEvent.setup();
    renderPage([HOLD_ROW]);

    await screen.findByRole("button", { name: /hold/i });
    const hold = screen.getByRole("button", { name: /hold/i });
    await user.click(hold);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm Hold" }));

    await waitFor(() => expect(recordPipelineDecision).toHaveBeenCalledWith("app-2", "hold", undefined));
  });

  it("submits a reject decision via confirmation modal", async () => {
    const user = userEvent.setup();
    renderPage([REJECT_ROW], ["/matching-results?jobId=j-1&group=lower_priority"]);

    await screen.findByRole("button", { name: /reject/i });
    const reject = screen.getByRole("button", { name: /reject/i });
    await user.click(reject);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm Reject" }));

    await waitFor(() => expect(recordPipelineDecision).toHaveBeenCalledWith("app-3", "reject", undefined));
  });

  it("highlights the shortcut matching the real backend status -> decision map", async () => {
    renderPage();

    await screen.findByRole("button", { name: /advance/i });
    expect(screen.getByRole("button", { name: /advance/i }).classList.contains("active")).toBe(true);
    expect(screen.getByRole("button", { name: /hold/i }).classList.contains("active")).toBe(false);
    expect(screen.getByRole("button", { name: /reject/i }).classList.contains("active")).toBe(false);
  });
});

describe("MatchingResults filters", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRanking.mockResolvedValue([ADVANCE_ROW, HOLD_ROW, OTHER_JOB_ROW]);
    recordPipelineDecision.mockResolvedValue({});
    getJobs.mockResolvedValue(jobList);
  });

  it("switches job and scopes to the newly selected job", async () => {
    const user = userEvent.setup();
    renderPage([ADVANCE_ROW, OTHER_JOB_ROW], ["/matching-results?jobId=j-1"]);

    await screen.findByText("Ada Lovelace");
    expect(screen.getByText("Ada Lovelace")).toBeTruthy();
    expect(screen.queryByText("Linus Pauling")).toBeNull();

    // Switch job via job select
    const jobSelect = screen.getByLabelText(/filter results by job/i);
    await user.selectOptions(jobSelect, "j-2");

    // Scoped to j-2
    expect(screen.queryByText("Ada Lovelace")).toBeNull();
    expect(screen.getByText("Linus Pauling")).toBeTruthy();
  });

  it("filters rows by minimum score and hides candidates below score", async () => {
    const user = userEvent.setup();
    renderPage([ADVANCE_ROW, HOLD_ROW], ["/matching-results?jobId=j-1"]);

    await screen.findByText("Ada Lovelace");
    const minScoreSelect = screen.getByLabelText(/filter results by minimum score/i);
    await user.selectOptions(minScoreSelect, "85");

    expect(screen.getByText("Ada Lovelace")).toBeTruthy();
    expect(screen.queryByText("Grace Hopper")).toBeNull();
  });
});

describe("MatchingResults row navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRanking.mockResolvedValue([ADVANCE_ROW]);
    recordPipelineDecision.mockResolvedValue({});
    getJobs.mockResolvedValue(jobList);
  });

  it("navigates to the review screen for the application", async () => {
    const user = userEvent.setup();
    renderWithRoutes([ADVANCE_ROW]);

    await screen.findByText("Ada Lovelace");
    await user.click(screen.getByText("Ada Lovelace"));

    await waitFor(() => expect(screen.getByText("REVIEW_SCREEN:app-1")).toBeTruthy());
  });
});

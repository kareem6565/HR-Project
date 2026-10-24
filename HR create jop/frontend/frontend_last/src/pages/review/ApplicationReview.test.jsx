import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ApplicationReview, { filterCertificationHeadings } from "./ApplicationReview";
import { getReviewWorkspace, recordDecision } from "../../services/reviewService";

// Verify the review screen keeps submitting the exact same payload through
// the shared PipelineActions component it previously sent with inline buttons:
// recordDecision(applicationId, decision, reason) -> { decision, reason }.
vi.mock("../../services/reviewService", () => ({
  getReviewWorkspace: vi.fn(),
  runEvaluation: vi.fn(),
  recordDecision: vi.fn(),
}));
vi.mock("../../services/resumeService", () => ({
  downloadResume: vi.fn(),
}));

const workspace = {
  application: {
    id: "app-1",
    status: "ready_for_review",
    created_at: "2025-01-10T00:00:00Z",
    resume_id: null,
  },
  candidate: {
    id: "c-1",
    name: "Ada Lovelace",
    email: "ada@example.com",
    location: "London",
    summary: "Full-stack engineer with 8 years of experience.",
    skills: ["Python", "React"],
  },
  job: {
    id: "j-1",
    title: "Backend Engineer",
    department: "Engineering",
  },
  evaluation: null,
  evidence: [],
  poolRow: { group: "A", decision: null },
  resume: null,
  profile: null,
};

function renderPage(initialEntry = "/applications/app-1/review", state = undefined) {
  const initialEntries = state ? [{ pathname: initialEntry, state }] : [initialEntry];
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/applications/:id/review" element={<ApplicationReview />} />
        <Route path="/matching" element={<div data-testid="matching-page">Matching Page</div>} />
        <Route path="/applications/:id/review" element={<ApplicationReview />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ApplicationReview pipeline decision", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getReviewWorkspace.mockResolvedValue(workspace);
    recordDecision.mockResolvedValue({});
  });

  it("submits { decision: 'hold', reason } via the shared component and confirmation modal", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "Ada Lovelace" });

    await user.click(screen.getByRole("button", { name: /hold/i }));
    expect(screen.getByText(/Confirm HR Decision: Hold/i)).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(/Enter reason for audit record/i), "waiting on references");
    await user.click(screen.getByRole("button", { name: /Confirm Hold/i }));

    await waitFor(() =>
      expect(recordDecision).toHaveBeenCalledWith("app-1", "hold", "waiting on references")
    );
  });

  it("submits { decision: 'advance' } with an empty reason", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "Ada Lovelace" });

    await user.click(screen.getByRole("button", { name: /advance/i }));
    await user.click(screen.getByRole("button", { name: /Confirm Advance/i }));

    await waitFor(() => expect(recordDecision).toHaveBeenCalledWith("app-1", "advance", ""));
  });

  it("does not submit anything when a decision is cancelled", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "Ada Lovelace" });

    await user.click(screen.getByRole("button", { name: /reject/i }));
    await user.click(screen.getByRole("button", { name: /Cancel/i }));

    expect(recordDecision).not.toHaveBeenCalled();
  });

  it("displays current recorded decision badge and timestamp when decision is present in poolRow", async () => {
    getReviewWorkspace.mockResolvedValueOnce({
      ...workspace,
      poolRow: {
        group: "must_review",
        decision: "advance",
        decision_created_at: "2025-01-15T12:00:00Z",
      },
    });

    renderPage();

    await screen.findByRole("heading", { name: "Ada Lovelace" });
    const badge = screen.getByTestId("current-decision-badge");
    expect(badge).toHaveTextContent("Advance");
    expect(screen.getByText(/\(Recorded on/i)).toBeInTheDocument();
  });

  it("prevents repeated submissions while request is pending", async () => {
    const user = userEvent.setup();
    let resolveDecision;
    recordDecision.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDecision = resolve;
        })
    );

    renderPage();
    await screen.findByRole("heading", { name: "Ada Lovelace" });

    await user.click(screen.getByRole("button", { name: /advance/i }));
    const confirmBtn = screen.getByRole("button", { name: /Confirm Advance/i });

    // Click once
    await user.click(confirmBtn);
    expect(confirmBtn).toBeDisabled();
    expect(confirmBtn).toHaveTextContent("Saving…");

    // Repeated click while disabled should not trigger extra recordDecision call
    await user.click(confirmBtn);
    expect(recordDecision).toHaveBeenCalledTimes(1);

    // Finish request
    resolveDecision({});
    await waitFor(() => expect(screen.queryByText("Confirm Advance")).not.toBeInTheDocument());
  });

  it("handles HTTP 409 conflict responses gracefully and offers reload button", async () => {
    const user = userEvent.setup();
    const error409 = new Error("Conflict");
    error409.response = {
      status: 409,
      data: { detail: "The referenced evaluation is stale and has been superseded." },
    };
    recordDecision.mockRejectedValueOnce(error409);

    renderPage();
    await screen.findByRole("heading", { name: "Ada Lovelace" });

    await user.click(screen.getByRole("button", { name: /advance/i }));
    await user.click(screen.getByRole("button", { name: /Confirm Advance/i }));

    // Verify conflict error message is rendered
    await screen.findByRole("alert");
    expect(
      screen.getByText(/Evaluation Conflict \(409\)/i)
    ).toBeInTheDocument();

    // Verify Reload button is present
    const reloadBtn = screen.getByRole("button", { name: /Reload Latest Evaluation/i });
    expect(reloadBtn).toBeInTheDocument();

    // Clicking reload refreshes the workspace
    await user.click(reloadBtn);
    expect(getReviewWorkspace).toHaveBeenCalledTimes(2);
  });

  it("navigates to next candidate on 'Save & Next Candidate' when candidateIds exist in location state", async () => {
    const user = userEvent.setup();
    const state = { candidateIds: ["app-1", "app-2"], jobId: "j-1" };
    renderPage("/applications/app-1/review", state);

    await screen.findByRole("heading", { name: "Ada Lovelace" });

    await user.click(screen.getByRole("button", { name: /advance/i }));
    const saveAndNextBtn = screen.getByRole("button", { name: /Save & Next Candidate/i });
    await user.click(saveAndNextBtn);

    await waitFor(() =>
      expect(recordDecision).toHaveBeenCalledWith("app-1", "advance", "")
    );
  });

  it("falls back to job matching results on 'Save & Next Candidate' when at the end of the list", async () => {
    const user = userEvent.setup();
    const state = { candidateIds: ["app-1"], jobId: "j-1" };
    renderPage("/applications/app-1/review", state);

    await screen.findByRole("heading", { name: "Ada Lovelace" });

    await user.click(screen.getByRole("button", { name: /advance/i }));
    const saveAndNextBtn = screen.getByRole("button", { name: /Save & Next Candidate/i });
    await user.click(saveAndNextBtn);

    await waitFor(() =>
      expect(recordDecision).toHaveBeenCalledWith("app-1", "advance", "")
    );
    await screen.findByTestId("matching-page");
  });

  it("renders unified evaluation summary, limitation note, and single evidence table when evaluation exists", async () => {
    getReviewWorkspace.mockResolvedValueOnce({
      ...workspace,
      evaluation: {
        id: "eval-99",
        version_number: 1,
        scoring_version: "v1.2",
        status: "completed",
        score: "78",
        created_at: "2025-01-12T10:00:00Z",
        explanation: {
          summary: "Strong candidate matching all must-have backend requirements.",
          points: ["Extensive Python experience", "Strong system design skills"],
        },
        score_breakdown: {
          "must_have:Python": {
            requirement_key: "must_have:Python",
            text: "Python Programming",
            category: "must_have",
            contribution: 40,
          },
        },
      },
      evidence: [
        {
          id: "ev-99",
          evidence_type: "matched",
          requirement_ref: {
            requirement_key: "must_have:Python",
            text: "Python Programming",
            category: "must_have",
          },
          candidate_evidence: {
            quote: "5 years Python developer",
            matched_terms: ["Python"],
          },
          strength: "strong",
        },
      ],
      poolRow: { group: "must_review", decision: null },
    });

    renderPage();

    await screen.findByRole("heading", { name: "Ada Lovelace" });

    expect(screen.getByText(/Applied for/)).toHaveTextContent("Backend Engineer");
    expect(screen.getByText("Processing status")).toBeInTheDocument();
    expect(screen.getByText("AI Evaluation Status")).toBeInTheDocument();
    expect(screen.getByText("AI Match Score (0–100)")).toBeInTheDocument();
    expect(screen.getByText("AI Review Category")).toBeInTheDocument();
    expect(screen.getByText("Human HR Decision")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Pipeline decisions" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Go to HR decision/i })).toHaveAttribute("href", "#hr-decision");
    expect(screen.getByRole("region", { name: "HR Hiring Decision" })).toHaveAttribute("id", "hr-decision");
    expect(screen.getByRole("button", { name: "Advance" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();

    // Evaluation summary is present
    expect(screen.getByText(/78% Match Score/i)).toBeInTheDocument();
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText("Scoring v1.2")).toBeInTheDocument();
    expect(screen.getByText("Why this score?")).toBeInTheDocument();
    expect(screen.getByText("Must Review")).toBeInTheDocument();

    // Limitation note is present
    expect(
      screen.getByText(
        "The evaluation reflects the text extracted from the CV and absence of evidence does not prove absence of the skill."
      )
    ).toBeInTheDocument();

    // Exactly one evidence table is rendered (no duplicate ScoreBreakdownTable or EvidenceSection)
    const tables = screen.getAllByRole("table");
    expect(tables).toHaveLength(1);

    // Requirement name is human readable (not raw key)
    expect(screen.getByText("Python Programming")).toBeInTheDocument();
    expect(screen.queryByText("must_have:Python")).not.toBeInTheDocument();

    // No raw JSON
    expect(screen.queryByText(/\{"/)).not.toBeInTheDocument();
  });

  it("keeps secondary profile details collapsed until the reviewer opens them", async () => {
    const user = userEvent.setup();
    getReviewWorkspace.mockResolvedValueOnce({
      ...workspace,
      profile: {
        profile_data: {
          education: ["University of London"],
          languages: ["English"],
          certifications: ["AWS Certified Solutions Architect"],
          linkedin_url: "linkedin.com/in/ada",
        },
      },
    });

    renderPage();
    await screen.findByRole("heading", { name: "Ada Lovelace" });

    const disclosure = screen.getByText("Additional profile details");
    expect(disclosure.parentElement).not.toHaveAttribute("open");
    expect(screen.getByText("University of London")).not.toBeVisible();

    await user.click(disclosure);
    expect(screen.getByText("University of London")).toBeVisible();
    expect(screen.getByRole("link", { name: "LinkedIn" })).toHaveAttribute(
      "href",
      "https://linkedin.com/in/ada"
    );
  });
});
describe("candidate certification display", () => {
  it("omits section headings from stored certifications while retaining credential names", () => {
    expect(filterCertificationHeadings([
      "PROFESSIONAL SUMMARY",
      "PROFESSIONAL EXPERIENCE",
      "AWS Certified Solutions Architect",
      "Professional Scrum Master I",
    ])).toEqual([
      "AWS Certified Solutions Architect",
      "Professional Scrum Master I",
    ]);
  });
});

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LimitationsNote from "./LimitationsNote";
import EvaluationSummary from "./EvaluationSummary";
import EvidenceTable from "./EvidenceTable";

describe("UI-05: LimitationsNote", () => {
  it("renders the stable limitation note disclosure with role='note'", () => {
    render(<LimitationsNote />);
    const note = screen.getByRole("note");
    expect(note).toBeInTheDocument();
    expect(note).toHaveTextContent(
      "The evaluation reflects the text extracted from the CV and absence of evidence does not prove absence of the skill."
    );
  });
});

describe("UI-05: EvaluationSummary", () => {
  const populatedEvaluation = {
    id: "eval-1",
    version_number: 2,
    scoring_version: "v1.2",
    status: "completed",
    score: "85",
    created_at: "2025-01-15T12:00:00Z",
    explanation: {
      summary: "Candidate meets core engineering requirements with demonstrated Python experience.",
      points: [
        "Strong backend development history with Python and Django.",
        { text: "Hands-on experience deploying containerized services." },
        { title: "Relational database expertise", summary: "PostgreSQL query tuning." },
      ],
    },
    provenance: {
      model: "gpt-4-turbo",
    },
  };

  it("renders authoritative score, group band, and versioning without raw JSON or provider name", () => {
    render(<EvaluationSummary evaluation={populatedEvaluation} group="must_review" />);

    // Score & Band
    expect(screen.getByText(/85% Match Score/i)).toBeInTheDocument();
    expect(screen.getByText(/\(Must Review\)/i)).toBeInTheDocument();

    // Versioning chips
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Version 2")).toBeInTheDocument();
    expect(screen.getByText("Scoring v1.2")).toBeInTheDocument();

    // Explanation section
    expect(screen.getByText("Why this score?")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Candidate meets core engineering requirements with demonstrated Python experience."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText("Strong backend development history with Python and Django.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Hands-on experience deploying containerized services.")
    ).toBeInTheDocument();

    // Provider name is NOT shown as primary user-facing content
    expect(screen.queryByText("gpt-4-turbo")).not.toBeInTheDocument();

    // No raw JSON stringify output
    expect(screen.queryByText(/\{"/)).not.toBeInTheDocument();
  });

  it("handles unscored / null score evaluation with dash and clear state", () => {
    const unscoredEvaluation = {
      ...populatedEvaluation,
      score: null,
    };

    render(<EvaluationSummary evaluation={unscoredEvaluation} />);

    expect(screen.getByText("No Score Recorded")).toBeInTheDocument();
    expect(
      screen.getByText("The backend recorded this evaluation without a numerical score.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/null%/i)).not.toBeInTheDocument();
  });

  it("renders re-evaluate button with loading state and calls onReevaluate", async () => {
    const user = userEvent.setup();
    const handleReevaluate = vi.fn();

    const { rerender } = render(
      <EvaluationSummary
        evaluation={populatedEvaluation}
        onReevaluate={handleReevaluate}
        evaluating={false}
      />
    );

    const btn = screen.getByRole("button", { name: /Re-run evaluation for this application/i });
    expect(btn).toBeInTheDocument();
    await user.click(btn);
    expect(handleReevaluate).toHaveBeenCalledTimes(1);

    // Re-render in evaluating state
    rerender(
      <EvaluationSummary
        evaluation={populatedEvaluation}
        onReevaluate={handleReevaluate}
        evaluating={true}
      />
    );
    expect(screen.getByText("Evaluating…")).toBeInTheDocument();
    expect(btn).toBeDisabled();
  });
});

describe("UI-05: EvidenceTable", () => {
  const populatedEvidence = [
    {
      id: "ev-1",
      evidence_type: "matched",
      requirement_ref: {
        requirement_key: "must_have:Python",
        text: "Python Programming",
        category: "must_have",
      },
      candidate_evidence: {
        quote: "Senior Python developer for 5 years building microservices.",
        matched_terms: ["Python", "microservices"],
        verification_status: "verified_quote",
        source_section: "experience",
      },
      strength: "strong",
    },
    {
      id: "ev-2",
      evidence_type: "partial",
      requirement_ref: {
        requirement_key: "important:Docker",
        skill: "Docker & Kubernetes",
        category: "important",
      },
      candidate_evidence: {
        quote: "Basic Docker containerization on personal projects.",
        explanation: "No Kubernetes experience recorded.",
        uncertainty: "Container orchestration not verified in professional roles.",
      },
      strength: "moderate",
    },
    {
      id: "ev-3",
      evidence_type: "missing",
      requirement_ref: {
        requirement_key: "must_have:Postgres",
        text: "PostgreSQL Database",
        category: "must_have",
      },
      candidate_evidence: null,
      strength: null,
    },
  ];

  const breakdown = {
    "must_have:Python": {
      requirement_key: "must_have:Python",
      text: "Python Programming",
      category: "must_have",
      contribution: 35,
    },
    "important:Docker": {
      requirement_key: "important:Docker",
      skill: "Docker & Kubernetes",
      category: "important",
      contribution: 15,
    },
    "must_have:Postgres": {
      requirement_key: "must_have:Postgres",
      text: "PostgreSQL Database",
      category: "must_have",
      contribution: 0,
    },
  };

  it("renders one unified evidence table with human-readable names and category labels", () => {
    render(<EvidenceTable evidence={populatedEvidence} breakdown={breakdown} />);

    // Exactly one primary table is rendered
    const tables = screen.getAllByRole("table");
    expect(tables).toHaveLength(1);

    // Summary counts chips
    expect(screen.getByText("1 supported")).toBeInTheDocument();
    expect(screen.getByText("1 partial")).toBeInTheDocument();
    expect(screen.getByText("1 no evidence found")).toBeInTheDocument();
    expect(screen.getByText("1 review signal")).toBeInTheDocument();

    // Human-readable requirement names
    expect(screen.getByText("Python Programming")).toBeInTheDocument();
    expect(screen.getByText("Docker & Kubernetes")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL Database")).toBeInTheDocument();

    // Category labels
    const mustHaveBadges = screen.getAllByText("Must-Have");
    expect(mustHaveBadges.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Important")).toBeInTheDocument();

    // Status chips
    expect(screen.getByText("Supported")).toBeInTheDocument();
    expect(screen.getByText("Partial")).toBeInTheDocument();
    expect(screen.getByText("No evidence found")).toBeInTheDocument();

    // Candidate evidence quotes
    expect(
      screen.getByText(/"Senior Python developer for 5 years building microservices."/)
    ).toBeInTheDocument();

    // Matched terms
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("microservices")).toBeInTheDocument();

    // Contribution & Strength
    expect(screen.getByText("Strong (+35%)")).toBeInTheDocument();
    expect(screen.getByText("Moderate (+15%)")).toBeInTheDocument();

    // Inline review signal for missing must-have
    expect(
      screen.getByText("No evidence found for must-have requirement")
    ).toBeInTheDocument();

    // Internal keys like "must_have:Python" or hashes are NOT displayed
    expect(screen.queryByText("must_have:Python")).not.toBeInTheDocument();
    expect(screen.queryByText("important:Docker")).not.toBeInTheDocument();
  });

  it("toggles expandable details drawer for supporting context", async () => {
    const user = userEvent.setup();
    render(<EvidenceTable evidence={populatedEvidence} breakdown={breakdown} />);

    // Initially, details drawer content is not visible
    expect(screen.queryByText("Resume Section:")).not.toBeInTheDocument();

    // Click "Details" on Python requirement
    const detailsButtons = screen.getAllByRole("button", { name: /details for/i });
    expect(detailsButtons.length).toBeGreaterThan(0);
    await user.click(detailsButtons[0]);

    // Now drawer content is displayed
    expect(screen.getByText("Resume Section:")).toBeInTheDocument();
    expect(screen.getByText("Experience")).toBeInTheDocument();
    expect(screen.getByText("Verification Status:")).toBeInTheDocument();
    expect(screen.getByText("Verified Quote")).toBeInTheDocument();

    // Click "Hide" collapses it
    const hideButton = screen.getByRole("button", { name: /hide details for/i });
    await user.click(hideButton);
    expect(screen.queryByText("Resume Section:")).not.toBeInTheDocument();
  });

  it("handles technical hash requirement keys by providing clean fallback names rather than raw keys", () => {
    const rawHashEvidence = [
      {
        id: "ev-hash-1",
        evidence_type: "matched",
        requirement_ref: {
          requirement_key: "req-0000000000000001",
        },
        candidate_evidence: {
          quote: "Python developer",
        },
      },
    ];

    render(<EvidenceTable evidence={rawHashEvidence} />);

    // Must NOT display "req-0000000000000001"
    expect(screen.queryByText("req-0000000000000001")).not.toBeInTheDocument();
    // Must display fallback requirement name
    expect(screen.getByText("Requirement #1")).toBeInTheDocument();
  });

  it("renders EmptyState when no evidence or breakdown is present", () => {
    render(<EvidenceTable evidence={[]} breakdown={null} />);

    expect(
      screen.getByText("No requirement evidence was attached to this evaluation.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("handles missing/null candidate evidence gracefully without throwing or displaying null/undefined", () => {
    const missingEvidence = [
      {
        id: "ev-null",
        evidence_type: "missing",
        requirement_ref: {
          text: "GraphQL API",
          category: "nice_to_have",
        },
        candidate_evidence: null,
      },
    ];

    render(<EvidenceTable evidence={missingEvidence} />);

    expect(screen.getByText("GraphQL API")).toBeInTheDocument();
    expect(screen.getByText("No evidence found in CV text")).toBeInTheDocument();
    expect(screen.queryByText("null")).not.toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
  });
});

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RankedCandidateList, { CandidateCell, GroupPill, ScoreCell, SkillsPreview } from "./RankedCandidateList";

const user = { id: "c-1", name: "Ada Lovelace" };

const baseColumns = [
  { key: "name", header: "Candidate", render: (r) => <CandidateCell name={r.name} /> },
  { key: "score", header: "AI Score", render: (r) => <ScoreCell score={r.score} /> },
];

describe("RankedCandidateList", () => {
  it("renders configured columns and rows", () => {
    render(<RankedCandidateList rows={[user]} columns={baseColumns} />);
    expect(screen.getByText("Candidate")).toBeInTheDocument();
    expect(screen.getByText("AI Score")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: /ada lovelace/i })).toBeInTheDocument();
  });

  it("renders the backend-provided score without calculating it", () => {
    const { rerender } = render(
      <RankedCandidateList rows={[{ ...user, score: 87 }]} columns={baseColumns} />
    );
    // Whole scores retain their concise numeric display.
    expect(screen.getByText("87")).toBeInTheDocument();

    // Decimal string precision is formatted for display without changing the API value.
    rerender(<RankedCandidateList rows={[{ ...user, score: "87.500" }]} columns={baseColumns} />);
    expect(screen.getByText("87.5")).toBeInTheDocument();

    // Unscored rows render the "Not scored" placeholder.
    rerender(<RankedCandidateList rows={[{ ...user, score: null }]} columns={baseColumns} />);
    expect(screen.getByText("Not scored")).toBeInTheDocument();
  });

  it("renders the backend group exactly as received", () => {
    const groupColumns = [
      { key: "group", header: "Group", render: (r) => <GroupPill group={r.group} /> },
    ];
    const { rerender } = render(
      <RankedCandidateList rows={[{ ...user, group: "must_review" }]} columns={groupColumns} />
    );
    // Known group renders its display label; the value itself is untouched.
    expect(screen.getByText("Must Review")).toBeInTheDocument();

    // Unknown groups render the raw backend value.
    rerender(<RankedCandidateList rows={[{ ...user, group: "legendary" }]} columns={groupColumns} />);
    expect(screen.getByText("legendary")).toBeInTheDocument();
  });

  it("renders only the configured columns", () => {
    render(<RankedCandidateList rows={[user]} columns={baseColumns} />);
    expect(screen.queryByText(/Role|Decision|Action/i)).not.toBeInTheDocument();
  });

  it("renders the loading state", () => {
    render(<RankedCandidateList loading loadingLabel="Loading evaluations..." rows={[]} columns={baseColumns} />);
    expect(screen.getByText("Loading evaluations...")).toBeInTheDocument();
  });

  it("renders the empty state when there are no rows", () => {
    render(<RankedCandidateList rows={[]} columns={baseColumns} emptyMessage="No candidates to show." />);
    expect(screen.getByText("No candidates to show.")).toBeInTheDocument();
  });

  it("renders the error state and retries", async () => {
    const onRetry = vi.fn();
    const userEventApi = userEvent.setup();
    render(
      <RankedCandidateList
        error
        errorMessage="Unable to load evaluations. Please try again."
        onRetry={onRetry}
        rows={[]}
        columns={baseColumns}
      />
    );
    expect(screen.getByText("Unable to load evaluations. Please try again.")).toBeInTheDocument();
    await userEventApi.click(screen.getByRole("button", { name: /try again|retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("triggers the row click callback", async () => {
    const onRowClick = vi.fn();
    const userEventApi = userEvent.setup();
    render(<RankedCandidateList rows={[user]} columns={baseColumns} onRowClick={onRowClick} />);
    await userEventApi.click(screen.getByRole("cell", { name: /ada lovelace/i }));
    expect(onRowClick).toHaveBeenCalledWith(user);
  });

  it("renders an action column and triggers the configured action callback", async () => {
    const onAction = vi.fn();
    const columns = [
      ...baseColumns,
      {
        key: "action",
        header: "Action",
        render: (r) => (
          <button type="button" onClick={() => onAction(r)}>
            Review
          </button>
        ),
      },
    ];
    const userEventApi = userEvent.setup();
    render(<RankedCandidateList rows={[user]} columns={columns} />);
    await userEventApi.click(screen.getByRole("button", { name: /review/i }));
    expect(onAction).toHaveBeenCalledWith(user);
  });

  it("renders the parent-owned toolbar slot", () => {
    render(
      <RankedCandidateList
        rows={[user]}
        columns={baseColumns}
        toolbar={<input placeholder="Search candidates..." />}
      />
    );
    expect(screen.getByPlaceholderText("Search candidates...")).toBeInTheDocument();
  });

  it("renders a header slot inside the panel for both filled and empty lists", () => {
    const header = <div className="panel-title">All Talent Pool Candidates</div>;
    const { rerender } = render(<RankedCandidateList rows={[user]} columns={baseColumns} header={header} />);
    expect(screen.getByText("All Talent Pool Candidates")).toBeInTheDocument();

    rerender(<RankedCandidateList rows={[]} columns={baseColumns} header={header} emptyMessage="Empty pool." />);
    expect(screen.getByText("All Talent Pool Candidates")).toBeInTheDocument();
    expect(screen.getByText("Empty pool.")).toBeInTheDocument();
  });
});

describe("RankedCandidateList display cells", () => {
  it("CandidateCell builds initials from the name", () => {
    render(<CandidateCell name="Alan Turing" subtitle={<span>turing@example.com</span>} />);
    expect(screen.getByText("AT")).toBeInTheDocument();
    expect(screen.getByText("Alan Turing")).toBeInTheDocument();
    expect(screen.getByText("turing@example.com")).toBeInTheDocument();
  });

  it("ScoreCell text variant renders a plain number, badge variant a ScoreBadge", () => {
    render(<ScoreCell score={85} variant="text" />);
    expect(screen.getByText("85")).toBeInTheDocument();
    render(<ScoreCell score={85} variant="badge" />);
    expect(screen.getAllByText("85").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Not scored")).not.toBeInTheDocument();
  });

  it("SkillsPreview shows the no-profile note when empty and an overflow counter", () => {
    render(<SkillsPreview skills={[]} />);
    expect(screen.getByText("No profile yet")).toBeInTheDocument();

    render(<SkillsPreview skills={["Python", "SQL", "Go", "Rust"]} />);
    expect(screen.getByText("+1")).toBeInTheDocument();
    expect(screen.queryByText("Rust")).not.toBeInTheDocument();
  });
});

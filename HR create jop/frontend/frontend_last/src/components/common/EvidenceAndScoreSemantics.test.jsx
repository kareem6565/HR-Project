import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import ScoreBadge, { groupForScore, toneForScore, labelForScore, BAND_CONFIG } from "./ScoreBadge";
import ScoreCard from "./ScoreCard";
import RankedCandidateList, { GroupPill, ScoreCell } from "./RankedCandidateList";

describe("UI-02: Backend Score Groups & Semantics", () => {
  it("maps scores to authoritative backend bands without arbitrary frontend thresholds", () => {
    // Phase 4.5 backend rules: >=70 must_review, >=40 consider, <40 lower_priority
    expect(groupForScore(90)).toBe("must_review");
    expect(groupForScore(70)).toBe("must_review");
    expect(groupForScore(69)).toBe("consider");
    expect(groupForScore(40)).toBe("consider");
    expect(groupForScore(39)).toBe("lower_priority");
    expect(groupForScore(0)).toBe("lower_priority");
    expect(groupForScore(null)).toBe("lower_priority");
    expect(groupForScore(undefined)).toBe("lower_priority");
  });

  it("uses non-punitive semantic tones: lower_priority is grey, never red", () => {
    expect(toneForScore(85)).toBe("green");
    expect(toneForScore(70)).toBe("green");
    expect(toneForScore(55)).toBe("amber");
    expect(toneForScore(40)).toBe("amber");
    expect(toneForScore(30)).toBe("grey");
    expect(toneForScore(null)).toBe("grey");

    // Red is reserved for human Reject decisions, not low scores
    expect(toneForScore(10)).not.toBe("red");
    expect(BAND_CONFIG.lower_priority.tone).toBe("grey");
  });

  it("renders ScoreBadge with score, band aria-label and title, and dash for null", () => {
    const { rerender } = render(<ScoreBadge value={78} />);
    const badge = screen.getByText("78");
    expect(badge).toHaveClass("score-badge-green");
    expect(badge).toHaveAttribute("aria-label", "Score: 78, Band: Must Review");

    rerender(<ScoreBadge value={45} />);
    const amberBadge = screen.getByText("45");
    expect(amberBadge).toHaveClass("score-badge-amber");
    expect(amberBadge).toHaveAttribute("aria-label", "Score: 45, Band: Consider");

    rerender(<ScoreBadge value={25} />);
    const greyBadge = screen.getByText("25");
    expect(greyBadge).toHaveClass("score-badge-grey");
    expect(greyBadge).toHaveAttribute("aria-label", "Score: 25, Band: Lower Priority");

    // Null score renders dash, not null or null%
    rerender(<ScoreBadge value={null} />);
    expect(screen.getByText("—")).toHaveClass("score-badge-grey");
  });

  it("honors backend-provided group override in ScoreBadge", () => {
    render(<ScoreBadge value={50} group="must_review" />);
    const badge = screen.getByText("50");
    expect(badge).toHaveClass("score-badge-green");
    expect(badge).toHaveAttribute("aria-label", "Score: 50, Band: Must Review");
  });

  it("renders companion band label when showLabel is true", () => {
    render(<ScoreBadge value={72} showLabel />);
    expect(screen.getByText("Must Review")).toHaveClass("recommendation-green");
  });

  it("renders GroupPill with grey tone for lower_priority", () => {
    const { rerender } = render(<GroupPill group="lower_priority" />);
    const pill = screen.getByText("Lower Priority");
    expect(pill).toHaveClass("recommendation-grey");
    expect(pill.className).not.toContain("recommendation-red");

    rerender(<GroupPill group="consider" />);
    expect(screen.getByText("Consider")).toHaveClass("recommendation-amber");

    rerender(<GroupPill group="must_review" />);
    expect(screen.getByText("Must Review")).toHaveClass("recommendation-green");
  });
});

describe("UI-02: Honest Evidence Labels and Neutral Styling", () => {
  it("renders missing requirement evidence with neutral styling and informative tooltip in ScoreCard", () => {
    render(
      <ScoreCard
        score={65}
        matching={["Python"]}
        partial={["Docker"]}
        missing={["Kubernetes"]}
      />
    );

    // Matching evidence has good chip
    const supported = screen.getByText("Python");
    expect(supported).toHaveClass("chip good");

    // Partial evidence has chip-partial
    const partial = screen.getByText("Docker");
    expect(partial).toHaveClass("chip chip-partial");

    // Missing evidence has neutral chip (never chip bad)
    const missing = screen.getByText("Kubernetes");
    expect(missing).toHaveClass("chip chip-neutral");
    expect(missing.className).not.toContain("bad");
    expect(missing).toHaveAttribute("title", "No evidence found in CV text: Kubernetes");
  });

  it("does not render bad-icon for missing evidence in ScoreCard", () => {
    const { container } = render(
      <ScoreCard
        score={72}
        missing={["AWS"]}
      />
    );

    // ScoreCard must use neutral-icon, not bad-icon
    expect(container.querySelector(".bad-icon")).toBeNull();
    expect(container.querySelector(".neutral-icon")).not.toBeNull();
  });

  it("keeps low-ranked and unscored candidates visible in candidate lists", () => {
    const rows = [
      { id: "1", name: "High Match", score: 92, group: "must_review" },
      { id: "2", name: "Borderline", score: 42, group: "consider" },
      { id: "3", name: "Low Match", score: 20, group: "lower_priority" },
      { id: "4", name: "Unscored New", score: null, group: "lower_priority" },
    ];

    const columns = [
      { key: "name", header: "Name", render: (r) => <span>{r.name}</span> },
      { key: "score", header: "Score", render: (r) => <ScoreCell score={r.score} group={r.group} /> },
      { key: "group", header: "Group", render: (r) => <GroupPill group={r.group} /> },
    ];

    render(<RankedCandidateList rows={rows} columns={columns} />);

    // All candidates, including low and unscored, are rendered and accessible
    expect(screen.getByText("High Match")).toBeInTheDocument();
    expect(screen.getByText("Borderline")).toBeInTheDocument();
    expect(screen.getByText("Low Match")).toBeInTheDocument();
    expect(screen.getByText("Unscored New")).toBeInTheDocument();
    expect(screen.getByText("Not scored")).toBeInTheDocument();
    expect(screen.getAllByText("Lower Priority")).toHaveLength(2);
  });
});

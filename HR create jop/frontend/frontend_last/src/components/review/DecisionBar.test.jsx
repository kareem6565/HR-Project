import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DecisionBar from "./DecisionBar";

describe("UI-06: DecisionBar Component", () => {
  it("renders 'No Decision Recorded' when no decision is currently set", () => {
    render(<DecisionBar currentDecision={null} onSelectDecision={vi.fn()} />);

    expect(screen.getByTestId("current-decision-badge")).toHaveTextContent("No Decision Recorded");
    expect(
      screen.getByText(/No HR decision recorded yet/i)
    ).toBeInTheDocument();

    // Verify labelled buttons are visible
    expect(screen.getByRole("button", { name: "Advance" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();

    // Verify decision integrity and audit notice
    expect(screen.getByText(/Decision Integrity:/i)).toBeInTheDocument();
  });

  it("displays recorded decision badge and timestamp when a decision exists", () => {
    render(
      <DecisionBar
        currentDecision="advance"
        decisionCreatedAt="2025-01-15T14:30:00Z"
        onSelectDecision={vi.fn()}
      />
    );

    const badge = screen.getByTestId("current-decision-badge");
    expect(badge).toHaveTextContent("Advance");
    expect(screen.getByText(/\(Recorded on/i)).toBeInTheDocument();

    // Check Advance button has aria-pressed='true'
    const advanceBtn = screen.getByRole("button", { name: "Advance" });
    expect(advanceBtn).toHaveAttribute("aria-pressed", "true");

    const holdBtn = screen.getByRole("button", { name: "Hold" });
    expect(holdBtn).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onSelectDecision when an action button is clicked", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    render(<DecisionBar currentDecision={null} onSelectDecision={handleSelect} />);

    await user.click(screen.getByRole("button", { name: "Reject" }));
    expect(handleSelect).toHaveBeenCalledWith("reject");
  });

  it("disables all action buttons when disabled={true}", () => {
    render(<DecisionBar currentDecision={null} onSelectDecision={vi.fn()} disabled={true} />);

    expect(screen.getByRole("button", { name: "Advance" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Hold" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  });

  it("keeps the decision status and audit information without duplicate actions", () => {
    render(
      <DecisionBar
        currentDecision={null}
        onSelectDecision={vi.fn()}
        showActions={false}
      />
    );

    expect(screen.getByTestId("current-decision-badge")).toHaveTextContent("No Decision Recorded");
    expect(screen.getByText(/Decision Integrity:/i)).toBeInTheDocument();
    expect(screen.getByText(/Decision actions are available in the review summary above/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Advance" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Hold" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });
});

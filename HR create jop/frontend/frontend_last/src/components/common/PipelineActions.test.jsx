import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PipelineActions from "./PipelineActions";

function getButtons() {
  return {
    advance: screen.getByRole("button", { name: /advance/i }),
    hold: screen.getByRole("button", { name: /hold/i }),
    reject: screen.getByRole("button", { name: /reject/i }),
  };
}

describe("PipelineActions", () => {
  it("calls onDecision('advance') when Advance is clicked", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();
    render(<PipelineActions currentStatus={undefined} onDecision={onDecision} />);
    await user.click(getButtons().advance);
    expect(onDecision).toHaveBeenCalledWith("advance");
  });

  it("calls onDecision('hold') when Hold is clicked", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();
    render(<PipelineActions currentStatus={undefined} onDecision={onDecision} />);
    await user.click(getButtons().hold);
    expect(onDecision).toHaveBeenCalledWith("hold");
  });

  it("calls onDecision('reject') when Reject is clicked", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();
    render(<PipelineActions currentStatus={undefined} onDecision={onDecision} />);
    await user.click(getButtons().reject);
    expect(onDecision).toHaveBeenCalledWith("reject");
  });

  it("disables every action when disabled is true", () => {
    render(<PipelineActions currentStatus={undefined} onDecision={vi.fn()} disabled />);
    const { advance, hold, reject } = getButtons();
    expect(advance).toBeDisabled();
    expect(hold).toBeDisabled();
    expect(reject).toBeDisabled();
  });

  it("does not call onDecision when disabled", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();
    render(<PipelineActions currentStatus={undefined} onDecision={onDecision} disabled />);
    await user.click(getButtons().advance);
    expect(onDecision).not.toHaveBeenCalled();
  });

  it("marks only the action matching currentStatus as active", () => {
    const { rerender } = render(<PipelineActions currentStatus="hold" onDecision={vi.fn()} />);
    expect(getButtons().hold.classList.contains("active")).toBe(true);
    expect(getButtons().advance.classList.contains("active")).toBe(false);
    expect(getButtons().reject.classList.contains("active")).toBe(false);

    rerender(<PipelineActions currentStatus="rejected" onDecision={vi.fn()} />);
    expect(getButtons().hold.classList.contains("active")).toBe(false);
    expect(getButtons().reject.classList.contains("active")).toBe(false);

    rerender(<PipelineActions currentStatus="reject" onDecision={vi.fn()} />);
    expect(getButtons().reject.classList.contains("active")).toBe(true);
  });

  it("hides text labels in small mode while keeping them reachable via title", () => {
    render(<PipelineActions currentStatus={undefined} onDecision={vi.fn()} size="small" />);
    const advance = screen.getByRole("button", { name: /advance/i });
    expect(advance.textContent).not.toContain("Advance");
    expect(advance).toHaveAttribute("title", "Advance");
  });
});
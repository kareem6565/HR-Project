import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import ApplicationsList from "./ApplicationsList";
import { getApplications } from "../../services/applicationService";

vi.mock("../../services/applicationService", () => ({ getApplications: vi.fn() }));

function LocationProbe() {
  const location = useLocation();
  return <p>Current route: {location.pathname}</p>;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Applications score formatting", () => {
  it("formats decimal and exponent scores and rejects malformed or out-of-range values", async () => {
    getApplications.mockResolvedValue([
      { id: "app-1", candidateName: "Ada", job: "Engineer", appliedAt: "2026-10-01", score: "81.579" },
      { id: "app-2", candidateName: "Grace", job: "Analyst", appliedAt: "2026-10-02", score: "8.1579e1" },
      { id: "app-3", candidateName: "Katherine", job: "Designer", appliedAt: "2026-10-03", score: "101" },
    ]);

    render(<MemoryRouter><ApplicationsList /></MemoryRouter>);

    expect(await screen.findAllByText("81.6%")).toHaveLength(2);
    expect(screen.getByText("—")).toBeTruthy();
  });

  it("separates processing, HR decision, and other filters while preserving API status filtering", async () => {
    const user = userEvent.setup();
    getApplications.mockResolvedValue([
      {
        id: "app-1",
        candidateName: "Ada Lovelace",
        job: "Engineer",
        appliedAt: "2026-10-01",
        score: "81.579",
        group: "must_review",
        status: "ready_for_review",
      },
    ]);

    render(<MemoryRouter><ApplicationsList /></MemoryRouter>);

    expect(screen.getByRole("group", { name: "Processing status" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "HR decision status" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Other status" })).toBeInTheDocument();
    expect(screen.getByText(/states mirrored when HR records Hold, Advance, or Reject/i)).toBeInTheDocument();
    expect(await screen.findByText("Must Review")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "AI Review Category" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Application State" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Analysis Pending" }));
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith("analysis_pending"));
    expect(screen.getByRole("button", { name: "Analysis Pending" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "Advanced" }));
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith("advanced"));
    expect(screen.getByRole("button", { name: "Advanced" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "All" }));
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith("all"));
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  });

  it("distinguishes no applications from an empty status filter and offers supported next actions", async () => {
    getApplications.mockResolvedValue([]);
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ApplicationsList />
        <LocationProbe />
      </MemoryRouter>
    );

    expect(await screen.findByText("No applications yet.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start screening" }));
    expect(screen.getByText("Current route: /candidates/screen")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Advanced" }));
    expect(await screen.findByText("No applications match this status.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show all applications" }));
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith("all"));
  });
});

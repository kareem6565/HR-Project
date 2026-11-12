import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import ApplicationsList from "./ApplicationsList";
import { getApplications } from "../../services/applicationService";

vi.mock("../../services/applicationService", () => ({ getApplications: vi.fn(), getApplicationJobs: vi.fn().mockResolvedValue([]) }));

const pageResult = (items) => ({ items, page: 1, pageSize: 20, total: items.length, pages: items.length ? 1 : 0 });

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
    getApplications.mockResolvedValue(pageResult([
      { id: "app-1", candidateName: "Ada", job: "Engineer", appliedAt: "2026-10-01", score: "81.579", screeningStatus: "completed" },
      { id: "app-2", candidateName: "Grace", job: "Analyst", appliedAt: "2026-10-02", score: "8.1579e1", screeningStatus: "completed" },
      { id: "app-3", candidateName: "Katherine", job: "Designer", appliedAt: "2026-10-03", score: "101", screeningStatus: "completed" },
    ]));

    render(<MemoryRouter><ApplicationsList /></MemoryRouter>);

    expect(await screen.findAllByText("81.6%")).toHaveLength(2);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("separates processing, HR decision, and other filters while preserving API status filtering", async () => {
    const user = userEvent.setup();
    getApplications.mockResolvedValue(pageResult([
      {
        id: "app-1",
        candidateName: "Ada Lovelace",
        job: "Engineer",
        appliedAt: "2026-10-01",
        score: "81.579",
        group: "must_review",
        status: "ready_for_review",
      },
    ]));

    render(<MemoryRouter><ApplicationsList /></MemoryRouter>);

    expect(screen.getByRole("group", { name: "Processing status" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "HR decision status" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Other status" })).toBeInTheDocument();
    expect(screen.getByText(/application states mirror an HR decision/i)).toBeInTheDocument();
    expect(await screen.findByText("Must Review")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "AI review" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "HR decision" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Analysis Pending" }));
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith(expect.objectContaining({ status: "analysis_pending", page: 1, page_size: 20 })));
    expect(screen.getByRole("button", { name: "Analysis Pending" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "Advanced" }));
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith(expect.objectContaining({ status: "advanced", page: 1, page_size: 20 })));
    expect(screen.getByRole("button", { name: "Advanced" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "All" }));
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith(expect.not.objectContaining({ status: expect.anything() })));
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  });

  it("distinguishes no applications from an empty status filter and offers supported next actions", async () => {
    getApplications.mockResolvedValue(pageResult([]));
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
    expect(await screen.findByText("No applications match these filters.")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Reset filters" })[0]);
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith(expect.not.objectContaining({ status: expect.anything() })));
  });

  it("sends dashboard filters to the server and resets them", async () => {
    getApplications.mockResolvedValue(pageResult([]));
    const user = userEvent.setup();
    render(<MemoryRouter><ApplicationsList /></MemoryRouter>);
    await user.type(screen.getByRole("searchbox", { name: "Search candidates or jobs" }), "Ada");
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith(expect.objectContaining({ search: "Ada", page: 1, page_size: 20 })));
    await user.selectOptions(screen.getByLabelText("CV processing"), "failed");
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith(expect.objectContaining({ search: "Ada", processing_status: "failed" })));
    await user.click(screen.getAllByRole("button", { name: "Reset filters" })[0]);
    await waitFor(() => expect(getApplications).toHaveBeenLastCalledWith(expect.not.objectContaining({ search: expect.anything(), processing_status: expect.anything() })));
  });
});

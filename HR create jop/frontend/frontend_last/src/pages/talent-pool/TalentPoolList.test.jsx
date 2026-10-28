import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import TalentPoolList from "./TalentPoolList";
import { getTalentPool } from "../../services/talentPoolService";

vi.mock("../../services/talentPoolService", () => ({
  getTalentPool: vi.fn(),
}));

const POOL_ROWS = [
  {
    id: "app-1",
    applicationId: "app-1",
    candidateId: "c-1",
    jobId: "j-1",
    name: "Grace Hopper",
    email: "grace@example.com",
    jobTitle: "Backend Engineer",
    group: "must_review",
    score: 88,
    status: "hold",
    decision: "advance",
    decisionCreatedAt: "2026-10-20T10:00:00Z",
    evidence: [{
      evidence_type: "matched",
      requirement: "Python",
      quote: "Built Python services.",
      quote_verified: true,
    }],
    skills: ["Python", "PostgreSQL"],
  },
];

function PathProbe() {
  return <span data-testid="path">{useLocation().pathname}</span>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/talent-pool"]}>
      <TalentPoolList />
      <PathProbe />
    </MemoryRouter>
  );
}

describe("TalentPoolList (RankedCandidateList integration)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTalentPool.mockResolvedValue(POOL_ROWS);
  });

  it("renders pool rows through the shared list without touching the API source", async () => {
    renderPage();

    expect(await screen.findByText("Grace Hopper")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Must Review")).toBeInTheDocument();
    expect(screen.getByText("Hold")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("Advance")).toBeInTheDocument();
    expect(screen.getAllByText("Python").length).toBeGreaterThan(0);
    expect(screen.getByText(/verified quote/i)).toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it("navigates to the application review on row click", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Grace Hopper");
    await user.click(screen.getByRole("cell", { name: /grace hopper/i }));

    expect(screen.getByTestId("path").textContent).toBe("/applications/app-1/review");
  });

  it("opens review from the action button too", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Grace Hopper");
    await user.click(screen.getByRole("button", { name: /review/i }));

    expect(screen.getByTestId("path").textContent).toBe("/applications/app-1/review");
  });

  it("keeps the in-panel search semantics in the page", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Grace Hopper");
    await user.type(screen.getByPlaceholderText("Search name, role, or skill..."), "zzz-none");

    expect(screen.getByText("No previous applications match your search.")).toBeInTheDocument();
  });

  it("finds previously reviewed candidates by stored profile skill", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Grace Hopper");
    await user.type(screen.getByPlaceholderText("Search name, role, or skill..."), "PostgreSQL");

    expect(screen.getByText("Grace Hopper")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
  });

  it("requests rejected applications only after the explicit filter is enabled", async () => {
    const user = userEvent.setup();
    const rejected = { ...POOL_ROWS[0], id: "app-2", name: "Katherine Johnson", status: "rejected" };
    getTalentPool.mockImplementation(({ includeRejected } = {}) =>
      Promise.resolve(includeRejected ? [...POOL_ROWS, rejected] : POOL_ROWS)
    );
    renderPage();

    await screen.findByText("Grace Hopper");
    expect(getTalentPool).toHaveBeenLastCalledWith({ includeRejected: false });

    await user.click(screen.getByRole("checkbox", { name: /include rejected applications/i }));
    await waitFor(() => expect(getTalentPool).toHaveBeenLastCalledWith({ includeRejected: true }));
    expect(await screen.findByText("Katherine Johnson")).toBeInTheDocument();
    expect(screen.getByText("Rejected for this role")).toBeInTheDocument();
  });

  it("shows the stored quote and criterion classification when expanded", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Grace Hopper");
    await user.click(screen.getByText(/verified quote/i));

    expect(screen.getByText("Built Python services.")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveTextContent("Python: matched");
    expect(screen.getByTestId("path").textContent).toBe("/talent-pool");
  });
});

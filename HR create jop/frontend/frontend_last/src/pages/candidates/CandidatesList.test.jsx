import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import CandidatesList from "./CandidatesList";
import { getCandidates } from "../../services/candidateService";

vi.mock("../../services/candidateService", () => ({ getCandidates: vi.fn() }));

function RouteProbe() {
  const location = useLocation();
  return <p>Current route: {location.pathname}</p>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/candidates"]}>
      <Routes>
        <Route path="/candidates" element={<CandidatesList />} />
        <Route path="/candidates/screen" element={<RouteProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

const candidate = {
  id: "candidate-1",
  name: "Ada Lovelace",
  email: "ada@example.com",
  status: "active",
  skills: ["Python"],
  experience: "2 positions",
  appliedAt: "2026-10-01",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Candidates empty states", () => {
  it("explains how candidates enter an empty roster and offers screening", async () => {
    getCandidates.mockResolvedValue([]);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText(/No candidates yet/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /New Screening/i }));
    expect(screen.getByText("Current route: /candidates/screen")).toBeInTheDocument();
  });

  it("keeps filtered-empty distinct and lets the user clear filters", async () => {
    getCandidates.mockResolvedValue([candidate]);
    const user = userEvent.setup();
    renderPage();

    const search = await screen.findByRole("textbox", { name: "Search candidates" });
    await user.type(search, "no matching person");
    expect(await screen.findByText(/No candidates match your search or status filter/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
  });
});

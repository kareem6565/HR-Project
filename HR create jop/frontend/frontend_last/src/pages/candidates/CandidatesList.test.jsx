import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import CandidatesList from "./CandidatesList";
import { archiveCandidate, getCandidates } from "../../services/candidateService";

vi.mock("../../services/candidateService", () => ({
  archiveCandidate: vi.fn(),
  getCandidates: vi.fn(),
}));

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

  it("requires confirmation, then archives a candidate out of the active roster", async () => {
    getCandidates.mockResolvedValue([candidate]);
    archiveCandidate.mockResolvedValue({ ...candidate, status: "archived" });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Archive Ada Lovelace" }));
    expect(screen.getByRole("dialog", { name: "Archive candidate?" })).toHaveTextContent(
      "applications, CVs, evaluations, and hiring decisions remain available"
    );
    expect(archiveCandidate).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(archiveCandidate).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "View candidate profile for Ada Lovelace" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Archive Ada Lovelace" }));
    await user.click(screen.getByRole("button", { name: "Archive candidate" }));

    expect(archiveCandidate).toHaveBeenCalledWith("candidate-1");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Ada Lovelace was archived. Their hiring history is retained."
    );
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter candidates by status" }), "archived");
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Archive Ada Lovelace" })).not.toBeInTheDocument();
  });

  it("keeps the candidate active and reports a failed archive request", async () => {
    getCandidates.mockResolvedValue([candidate]);
    archiveCandidate.mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Archive Ada Lovelace" }));
    await user.click(screen.getByRole("button", { name: "Archive candidate" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not archive this candidate. Please try again."
    );
    expect(screen.getByRole("link", { name: "View candidate profile for Ada Lovelace" })).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CandidateDetails from "./CandidateDetails";
import { getCandidateById } from "../../services/candidateService";
import { findCandidateApplications } from "../../services/interviewQuestionSetService";
import {
  createTalentPoolConsentLink,
  withdrawTalentPoolConsent,
} from "../../services/talentPoolService";

vi.mock("../../services/candidateService", () => ({
  getCandidateById: vi.fn(),
  updateCandidate: vi.fn(),
}));
vi.mock("../../services/interviewQuestionSetService", () => ({
  findCandidateApplications: vi.fn(),
}));
vi.mock("../../services/talentPoolService", () => ({
  createTalentPoolConsentLink: vi.fn(),
  withdrawTalentPoolConsent: vi.fn(),
}));

function renderDetails() {
  return render(
    <MemoryRouter initialEntries={["/candidates/candidate-1"]}>
      <Routes>
        <Route path="/candidates/:id" element={<CandidateDetails />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("CandidateDetails Talent Pool consent controls", () => {
  beforeEach(() => {
    getCandidateById.mockResolvedValue({ id: "candidate-1", name: "Synthetic Candidate", skills: [] });
    findCandidateApplications.mockResolvedValue([]);
  });

  it("lets HR create a one-time link without recording consent", async () => {
    createTalentPoolConsentLink.mockResolvedValue({
      url: "http://localhost:5174/talent-pool/consent#opaque-token",
      expiresAt: "2026-11-01T00:00:00Z",
    });
    const user = userEvent.setup();
    renderDetails();

    await user.click(await screen.findByRole("button", { name: "Create consent link" }));

    expect(createTalentPoolConsentLink).toHaveBeenCalledWith("candidate-1");
    expect(withdrawTalentPoolConsent).not.toHaveBeenCalled();
    expect(await screen.findByLabelText("One-time link")).toHaveValue(
      "http://localhost:5174/talent-pool/consent#opaque-token",
    );
    expect(screen.getByRole("status")).toHaveTextContent(/expires in 7 days/i);
  });

  it("records withdrawal only after the HR user confirms the candidate request", async () => {
    withdrawTalentPoolConsent.mockResolvedValue(true);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    renderDetails();

    await user.click(await screen.findByRole("button", { name: "Record candidate withdrawal" }));
    expect(withdrawTalentPoolConsent).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Record candidate withdrawal" }));
    expect(withdrawTalentPoolConsent).toHaveBeenCalledWith("candidate-1");
    expect(await screen.findByRole("status")).toHaveTextContent(/no longer eligible/i);
  });
});

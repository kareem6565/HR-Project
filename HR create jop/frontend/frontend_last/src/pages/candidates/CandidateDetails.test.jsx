import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useSearchParams,
} from "react-router-dom";
import CandidateDetails from "./CandidateDetails";
import { getCandidateById } from "../../services/candidateService";
import { findCandidateApplications } from "../../services/interviewQuestionSetService";

vi.mock("../../services/candidateService", () => ({
  getCandidateById: vi.fn(),
  updateCandidate: vi.fn(),
}));

vi.mock("../../services/interviewQuestionSetService", () => ({
  findCandidateApplications: vi.fn(),
  saveSelectedQuestions: vi.fn(),
  listQuestionSets: vi.fn(),
  createQuestionSet: vi.fn(),
  updateQuestionSet: vi.fn(),
}));

const CANDIDATE = {
  id: "c-1",
  name: "Ada Lovelace",
  email: "ada@example.com",
  phone: "",
  experience: "",
  title: "",
  summary: "",
  skills: [],
  linkedin: null,
  github: null,
  portfolio: null,
  cv: null,
};

function LocationProbe() {
  const location = useLocation();
  const [params] = useSearchParams();
  return (
    <span data-testid="path">
      {location.pathname}?{params.toString()}
    </span>
  );
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/candidates/c-1"]}>
      <Routes>
        <Route path="/candidates/:id" element={<CandidateDetails />} />
        <Route path="*" element={null} />
      </Routes>
      <LocationProbe />
    </MemoryRouter>
  );
}

describe("CandidateDetails application-aware question prep entry", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCandidateById.mockResolvedValue(CANDIDATE);
  });

  it("navigates straight to prep when the candidate has exactly one application", async () => {
    findCandidateApplications.mockResolvedValue([
      { id: "app-1", jobTitle: "Backend Engineer", status: "created" },
    ]);
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Ada Lovelace");
    await screen.findByRole("button", { name: /Backend Engineer/ });
    await user.click(screen.getByRole("button", { name: /Prepare questions/ }));

    await screen.findByText(/interview-questions\?applicationId=app-1/);
    expect(screen.getByTestId("path").textContent).toBe("/interview-questions?applicationId=app-1");
    expect(findCandidateApplications).toHaveBeenCalledWith("c-1");
  });

  it("opens a chooser for multiple applications and navigates on selection", async () => {
    findCandidateApplications.mockResolvedValue([
      { id: "app-1", jobTitle: "Backend Engineer", status: "active" },
      { id: "app-2", jobTitle: "Data Engineer", status: "hold" },
    ]);
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Ada Lovelace");
    await screen.findByRole("button", { name: /Backend Engineer/ });
    await user.click(screen.getByRole("button", { name: /Prepare questions/ }));

    expect(
      await screen.findByText(/Pick the role you want to prepare questions for/i)
    ).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /Data Engineer/ }).at(-1));

    expect(screen.getByTestId("path").textContent).toBe("/interview-questions?applicationId=app-2");
  });

  it("explains when the candidate has no applications", async () => {
    findCandidateApplications.mockResolvedValue([]);
    renderPage();

    await screen.findByText("Ada Lovelace");
    expect(await screen.findByText(/No job applications are linked to this candidate yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Prepare questions/ })).toBeDisabled();
    expect(screen.getByTestId("path").textContent).toBe("/candidates/c-1?");
  });

  it("opens the matching application review from the candidate profile", async () => {
    findCandidateApplications.mockResolvedValue([
      { id: "app-1", jobTitle: "Backend Engineer", status: "advanced", createdAt: "2026-10-01T10:00:00Z" },
    ]);
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Ada Lovelace");
    await user.click(await screen.findByRole("button", { name: /Backend Engineer/ }));

    expect(screen.getByTestId("path").textContent).toBe("/applications/app-1/review?");
  });

  it("labels profile contact values that came from the CV", async () => {
    getCandidateById.mockResolvedValue({
      ...CANDIDATE,
      email: "",
      profileEmail: "ada.cv@example.com",
    });
    findCandidateApplications.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Email (from CV)")).toBeInTheDocument();
    expect(screen.getByText("ada.cv@example.com")).toBeInTheDocument();
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation, useSearchParams } from "react-router-dom";
import InterviewQuestions from "./InterviewQuestions";
import { getCandidateById } from "../../services/candidateService";
import { getReviewBundle } from "../../services/reviewService";
import {
  getInterviewQuestions,
} from "../../services/interviewQuestionService";
import {
  listQuestionSets,
  saveSelectedQuestions,
} from "../../services/interviewQuestionSetService";

vi.mock("../../services/candidateService", () => ({
  getCandidateById: vi.fn(),
  updateCandidate: vi.fn(),
}));

vi.mock("../../services/reviewService", () => ({
  getReviewBundle: vi.fn(),
}));

vi.mock("../../services/interviewQuestionService", () => ({
  getInterviewQuestions: vi.fn(),
}));

vi.mock("../../services/interviewQuestionSetService", () => ({
  listQuestionSets: vi.fn(),
  saveSelectedQuestions: vi.fn(),
  findCandidateApplications: vi.fn(),
  createQuestionSet: vi.fn(),
  updateQuestionSet: vi.fn(),
}));

const QUESTIONS = {
  categories: ["Technical", "Behavioral", "Candidate-Specific"],
  questions: {
    Technical: [
      { id: "t1", text: "Design a REST API." },
      { id: "t2", text: "Explain an indexing strategy." },
    ],
    Behavioral: [{ id: "b1", text: "Tell me about a failure you learned from." }],
    "Candidate-Specific": [
      {
        id: "cs-gap-c1",
        text: "This role expects Distributed Systems experience, which isn't on your resume.",
      },
    ],
  },
  candidate_id: "c-1",
};

const BUNDLE = {
  application: { id: "app-1" },
  candidate: { id: "c-1", name: "Ada Lovelace" },
  job: { title: "Backend Engineer" },
  evaluations: [],
  evaluation: null,
  evidence: [],
  poolRow: null,
};

const CANDIDATE = { id: "c-1", name: "Ada Lovelace", email: "ada@example.com" };

function LocationProbe() {
  const location = useLocation();
  const [params] = useSearchParams();
  return (
    <span data-testid="path">
      {location.pathname}?{params.toString()}
    </span>
  );
}

function renderPage(route) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <InterviewQuestions />
      <LocationProbe />
    </MemoryRouter>
  );
}

describe("InterviewQuestions (application-scoped prep)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getInterviewQuestions.mockResolvedValue(QUESTIONS);
  });

  it("renders banks and updates the selection count", async () => {
    listQuestionSets.mockResolvedValue({ total: 0, currentId: null, questionSets: [] });
    getReviewBundle.mockResolvedValue(BUNDLE);
    const user = userEvent.setup();
    renderPage("/interview-questions?applicationId=app-1");

    await screen.findByText("Design a REST API.");
    expect(screen.getByText(/Ada Lovelace · Backend Engineer/)).toBeInTheDocument();

    await user.click(screen.getByText("Design a REST API."));
    expect(screen.getByText("1 selected")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Candidate-Specific/ }));
    await user.click(screen.getByText(/Distributed Systems experience/));
    expect(screen.getByText("2 selected")).toBeInTheDocument();
  });

  it("keeps browser-only mode disabled when no application is set", async () => {
    getCandidateById.mockResolvedValue(CANDIDATE);
    const user = userEvent.setup();
    renderPage("/interview-questions?candidateId=c-1");

    await screen.findByText("Design a REST API.");
    await user.click(screen.getByText("Design a REST API."));

    expect(screen.getByRole("button", { name: /Save Selected Questions \(1\)/ })).toBeDisabled();
    expect(screen.getByText(/browse-only preview/i)).toBeInTheDocument();
  });

  it("saves a new HR draft on the explicit application and opens the builder", async () => {
    listQuestionSets.mockResolvedValue({ total: 0, currentId: null, questionSets: [] });
    getReviewBundle.mockResolvedValue(BUNDLE);
    saveSelectedQuestions.mockResolvedValue({
      versionNumber: 1,
      status: "generated",
      questions: [
        { text: "Design a REST API." },
        {
          text: "This role expects Distributed Systems experience, which isn't on your resume.",
        },
      ],
    });
    const user = userEvent.setup();
    renderPage("/interview-questions?applicationId=app-1");

    await screen.findByText("Design a REST API.");
    await user.click(screen.getByText("Design a REST API."));
    await user.click(screen.getByRole("button", { name: /Candidate-Specific/ }));
    await user.click(screen.getByText(/Distributed Systems experience/));
    await user.click(screen.getByRole("button", { name: /Save Selected Questions \(2\)/ }));

    expect(await screen.findByText(/Saved draft v1 \(2 questions\)/)).toBeInTheDocument();
    expect(saveSelectedQuestions).toHaveBeenCalledWith("app-1", [
      { category: "technical", text: "Design a REST API.", topic: "", requirementKey: null },
      {
        category: "candidate_specific",
        text: "This role expects Distributed Systems experience, which isn't on your resume.",
        topic: "",
        requirementKey: null,
      },
    ]);

    await user.click(screen.getByRole("button", { name: "Open Question Set Builder" }));
    expect(screen.getByTestId("path").textContent).toBe("/applications/app-1/questions?");
  });

  it("never touches an approved set: saving still creates a fresh draft and says so", async () => {
    listQuestionSets.mockResolvedValue({
      total: 1,
      currentId: "set-approved",
      questionSets: [
        {
          id: "set-approved",
          jobApplicationId: "app-1",
          versionNumber: 2,
          status: "approved",
          isCurrent: true,
          questions: [],
        },
      ],
    });
    getReviewBundle.mockResolvedValue(BUNDLE);
    saveSelectedQuestions.mockResolvedValue({
      versionNumber: 3,
      status: "generated",
      questions: [{ text: "Design a REST API." }],
    });
    const user = userEvent.setup();
    renderPage("/interview-questions?applicationId=app-1");

    await screen.findByText("Design a REST API.");
    await user.click(screen.getByText("Design a REST API."));
    await user.click(screen.getByRole("button", { name: /Save Selected Questions/ }));

    expect(
      await screen.findByText(/The approved set was left untouched/i)
    ).toBeInTheDocument();
  });

  it("shows an error text when saving fails", async () => {
    listQuestionSets.mockResolvedValue({ total: 0, currentId: null, questionSets: [] });
    getReviewBundle.mockResolvedValue(BUNDLE);
    saveSelectedQuestions.mockRejectedValue({
      response: { data: { detail: "Application does not exist." } },
    });
    const user = userEvent.setup();
    renderPage("/interview-questions?applicationId=app-1");

    await screen.findByText("Design a REST API.");
    await user.click(screen.getByText("Design a REST API."));
    await user.click(screen.getByRole("button", { name: /Save Selected Questions/ }));

    expect(await screen.findByText("Application does not exist.")).toBeInTheDocument();
  });
});
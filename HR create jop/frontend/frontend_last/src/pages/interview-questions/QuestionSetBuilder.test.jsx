import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import QuestionSetBuilder from "./QuestionSetBuilder";
import { getReviewBundle } from "../../services/reviewService";
import { listQuestionSets } from "../../services/interviewQuestionSetService";

vi.mock("../../services/reviewService", () => ({ getReviewBundle: vi.fn() }));
vi.mock("../../services/interviewQuestionSetService", () => ({
  generateQuestionSet: vi.fn(),
  listQuestionSets: vi.fn(),
  updateQuestionSet: vi.fn(),
  approveQuestionSet: vi.fn(),
}));

const bundle = {
  candidate: { name: "Synthetic Candidate" },
  job: { title: "Backend Engineer" },
};

function renderBuilder() {
  return render(
    <MemoryRouter initialEntries={["/applications/app-1/questions"]}>
      <Routes>
        <Route path="/applications/:id/questions" element={<QuestionSetBuilder />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("QuestionSetBuilder review guidance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getReviewBundle.mockResolvedValue(bundle);
  });

  it("shows the source basis, exact quote, and consistent rubric", async () => {
    listQuestionSets.mockResolvedValue({
      total: 1,
      questionSets: [{
        id: "set-1",
        versionNumber: 1,
        status: "approved",
        statusLabel: "Approved",
        isCurrent: true,
        generatedBy: "ollama:gemma4:31b",
        createdAt: "2026-10-24T10:00:00Z",
        questions: [{
          id: "q-1",
          categoryLabel: "Technical",
          text: "How did you use PostgreSQL?",
          reviewGuide: {
            evidenceBasis: "verified_cv_evidence",
            purpose: "Explore the documented database project.",
            sourceQuote: "Built PostgreSQL services handling 2M records.",
            interviewerLooksFor: "A concrete example and validation method.",
            evaluationRubric: ["Clear sequence", "Relevant example"],
          },
        }],
      }],
    });

    renderBuilder();

    expect(await screen.findByText("How did you use PostgreSQL?")).toBeInTheDocument();
    expect(screen.getByText("Verified CV evidence")).toBeInTheDocument();
    expect(screen.getByText(/Built PostgreSQL services handling 2M records\./)).toBeInTheDocument();
    expect(screen.getByText("Consistent rubric")).toBeInTheDocument();
    expect(screen.getByText("Clear sequence")).toBeInTheDocument();
  });

  it("marks legacy questions without structured guidance clearly", async () => {
    listQuestionSets.mockResolvedValue({
      total: 1,
      questionSets: [{
        id: "legacy-set",
        versionNumber: 1,
        status: "approved",
        statusLabel: "Approved",
        isCurrent: true,
        questions: [{ id: "legacy-q", categoryLabel: "Technical", text: "Legacy question" }],
      }],
    });

    renderBuilder();

    expect(await screen.findByText("Legacy question")).toBeInTheDocument();
    expect(screen.getByText(/No structured review guidance is available/)).toBeInTheDocument();
  });
});

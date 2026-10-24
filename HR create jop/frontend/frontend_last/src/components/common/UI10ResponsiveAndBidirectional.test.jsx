import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import fs from "fs";
import path from "path";

import { CandidateCell } from "./RankedCandidateList";
import EvidenceTable from "../evaluation/EvidenceTable";
import ScoreCard from "./ScoreCard";
import MainLayout from "../../layouts/MainLayout";
import { AuthContext } from "../../context/AuthContext";

describe("HERA UI-10: Responsive, Bidirectional Text (dir='auto'), and Visual QA", () => {
  describe("Bidirectional Text Support (dir='auto') at Data Boundaries", () => {
    it("renders candidate name in CandidateCell with dir='auto' for mixed Arabic/English support", () => {
      render(
        <CandidateCell
          name="أحمد علي (Ahmed Ali)"
          subtitle="Software Engineer"
        />
      );

      const nameEl = screen.getByText("أحمد علي (Ahmed Ali)");
      expect(nameEl).toHaveAttribute("dir", "auto");
    });

    it("renders requirement names and quotes in EvidenceTable with dir='auto'", () => {
      const mockEvidence = [
        {
          id: "ev-1",
          requirement_ref: {
            requirement_key: "req-python",
            text: "خبرة في لغة بايثون (Python Experience)",
            category: "must_have",
          },
          evidence_type: "matched",
          candidate_evidence: {
            quote: "عملت كمهندس برمجيات بايثون لمدة 5 سنوات",
            mainText: "Python development experience",
          },
        },
      ];

      render(
        <EvidenceTable
          evidence={mockEvidence}
          breakdown={{}}
        />
      );

      const reqName = screen.getByText(/خبرة في لغة بايثون/);
      expect(reqName).toHaveAttribute("dir", "auto");

      const quote = screen.getByText(/عملت كمهندس برمجيات بايثون/);
      expect(quote).toHaveAttribute("dir", "auto");
    });

    it("renders requirement chips in ScoreCard with dir='auto'", () => {
      render(
        <ScoreCard
          score={88}
          matching={["بايثون (Python)", "FastAPI"]}
          partial={["Docker"]}
          missing={["Kubernetes"]}
        />
      );

      const matchingChip = screen.getByText("بايثون (Python)");
      expect(matchingChip).toHaveAttribute("dir", "auto");

      const partialChip = screen.getByText("Docker");
      expect(partialChip).toHaveAttribute("dir", "auto");

      const missingChip = screen.getByText("Kubernetes");
      expect(missingChip).toHaveAttribute("dir", "auto");
    });
  });

  describe("Chatbot Workflow Isolation (MainLayout)", () => {
    const renderWithRoute = (initialPath) => {
      const authValues = {
        isAuthenticated: true,
        isAdmin: true,
        isRecruiter: false,
        user: { id: "u-1", email: "admin@hera.ai", role: "admin" },
        logout: vi.fn(),
        checkAuth: vi.fn(),
      };

      return render(
        <AuthContext.Provider value={authValues}>
          <MemoryRouter initialEntries={[initialPath]}>
            <MainLayout />
          </MemoryRouter>
        </AuthContext.Provider>
      );
    };

    it("keeps chatbot OUT of the primary screening page (/candidates/screen)", () => {
      renderWithRoute("/candidates/screen");
      expect(screen.queryByRole("button", { name: /open hera chat/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /close hera chat/i })).not.toBeInTheDocument();
    });

    it("keeps chatbot OUT of application review (/applications/app-1/review)", () => {
      renderWithRoute("/applications/app-1/review");
      expect(screen.queryByRole("button", { name: /open hera chat/i })).not.toBeInTheDocument();
    });

    it("keeps chatbot OUT of job matching results (/matching-results)", () => {
      renderWithRoute("/matching-results");
      expect(screen.queryByRole("button", { name: /open hera chat/i })).not.toBeInTheDocument();
    });

    it("renders chatbot on secondary/overview pages like /dashboard", () => {
      renderWithRoute("/dashboard");
      expect(screen.getByRole("button", { name: /open hera assistant/i })).toBeInTheDocument();
    });
  });

  describe("CSS Responsive, Focus, and Reduced Motion Foundation (index.css)", () => {
    it("defines table-wrap overflow containment to prevent page-level horizontal scroll", () => {
      const cssPath = path.resolve(__dirname, "../../index.css");
      const cssContent = fs.readFileSync(cssPath, "utf-8");

      expect(cssContent).toContain(".table-wrap");
      expect(cssContent).toContain("overflow-x: auto");
      expect(cssContent).toContain("-webkit-overflow-scrolling: touch");
    });

    it("defines keyboard focus visible indicators (:focus-visible)", () => {
      const cssPath = path.resolve(__dirname, "../../index.css");
      const cssContent = fs.readFileSync(cssPath, "utf-8");

      expect(cssContent).toContain(":focus-visible");
      expect(cssContent).toContain("outline:");
    });

    it("supports prefers-reduced-motion: reduce", () => {
      const cssPath = path.resolve(__dirname, "../../index.css");
      const cssContent = fs.readFileSync(cssPath, "utf-8");

      expect(cssContent).toContain("prefers-reduced-motion: reduce");
      expect(cssContent).toContain("animation-duration: 0.01ms !important");
    });

    it("defines responsive layout adjustments for small mobile viewports (max-width: 480px)", () => {
      const cssPath = path.resolve(__dirname, "../../index.css");
      const cssContent = fs.readFileSync(cssPath, "utf-8");

      expect(cssContent).toContain("@media (max-width: 480px)");
      expect(cssContent).toContain(".main {");
    });
  });
});

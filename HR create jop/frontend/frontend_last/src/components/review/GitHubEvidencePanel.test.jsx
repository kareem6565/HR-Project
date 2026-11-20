import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GitHubEvidencePanel from "./GitHubEvidencePanel";
import {
  getLatestGitHubEvidence,
  requestGitHubEvidenceConsent,
  retryGitHubEvidence,
} from "../../services/githubEvidenceService";

vi.mock("../../services/githubEvidenceService", () => ({
  getLatestGitHubEvidence: vi.fn(),
  requestGitHubEvidenceConsent: vi.fn(),
  retryGitHubEvidence: vi.fn(),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("GitHubEvidencePanel", () => {
  it("requests candidate permission before starting the public review", async () => {
    getLatestGitHubEvidence.mockResolvedValue(null);
    requestGitHubEvidenceConsent.mockResolvedValue({
      analysis_id: "analysis-1", status: "awaiting_consent", consent_url: "/github-evidence/consent#opaque-token",
    });
    const user = userEvent.setup();
    render(<GitHubEvidencePanel applicationId="app-1" githubUrl="https://github.com/alex" />);
    await user.click(await screen.findByRole("button", { name: /request candidate consent/i }));
    expect(requestGitHubEvidenceConsent).toHaveBeenCalledWith("app-1", ["https://github.com/alex"]);
    expect(await screen.findByText(/analysis starts only after they agree/i)).toBeInTheDocument();
    expect(await screen.findByLabelText(/share this one-time consent link/i)).toHaveValue(
      `${window.location.origin}/github-evidence/consent#opaque-token`,
    );
  });

  it("distinguishes insufficient completed evidence from a failed request", async () => {
    getLatestGitHubEvidence.mockResolvedValue({
      id: "analysis-2", status: "completed", attempts: 1, evidence: [],
      assessments: [{
        requirement_key: "req-1", requirement_text: "Python", requirement_category: "must_have",
        classification: "insufficient", evidence_ids: [], explanation: "No relevant public artifact was found.", limitations: [],
      }],
    });
    const { rerender } = render(<GitHubEvidencePanel applicationId="app-2" githubUrl="" />);
    expect(await screen.findByText(/No sufficient public evidence was found/i)).toBeInTheDocument();
    getLatestGitHubEvidence.mockResolvedValue({
      id: "analysis-3", status: "failed", error_code: "RATE_LIMITED", attempts: 1, evidence: [], assessments: [],
    });
    rerender(<GitHubEvidencePanel applicationId="app-3" githubUrl="" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/No evidence conclusion was produced/i);
    expect(screen.queryByText(/No sufficient public evidence was found/i)).not.toBeInTheDocument();
    expect(retryGitHubEvidence).not.toHaveBeenCalled();
  });
});

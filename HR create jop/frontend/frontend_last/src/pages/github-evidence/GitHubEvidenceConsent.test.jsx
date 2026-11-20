import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GitHubEvidenceConsent from "./GitHubEvidenceConsent";
import {
  previewGitHubEvidenceConsent,
  respondToGitHubEvidenceConsent,
} from "../../services/githubEvidenceService";

vi.mock("../../services/githubEvidenceService", () => ({
  previewGitHubEvidenceConsent: vi.fn(),
  respondToGitHubEvidenceConsent: vi.fn(),
}));

afterEach(() => { cleanup(); window.location.hash = ""; vi.clearAllMocks(); });

describe("GitHubEvidenceConsent", () => {
  it("requires a self-attested candidate choice and records acceptance", async () => {
    window.location.hash = "#candidate-consent-token";
    previewGitHubEvidenceConsent.mockResolvedValue({
      organization_name: "HERA Test Org",
      consent_text: "Review public repository information for this role.",
      consent_version: "test-v1",
      repository_urls: ["https://github.com/alex/demo"],
      link_expires_at: "2026-11-30T00:00:00Z",
    });
    respondToGitHubEvidenceConsent.mockResolvedValue({ status: "pending" });
    const user = userEvent.setup();
    render(<GitHubEvidenceConsent />);
    expect(await screen.findByText(/Review public repository information/i)).toBeInTheDocument();
    expect(respondToGitHubEvidenceConsent).not.toHaveBeenCalled();
    const agree = screen.getByRole("button", { name: /I agree/i });
    expect(agree).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /I am the candidate/i }));
    await user.click(agree);
    expect(respondToGitHubEvidenceConsent).toHaveBeenCalledWith("candidate-consent-token", "accepted");
    expect(await screen.findByRole("status")).toHaveTextContent(/permission is recorded/i);
  });

  it("shows invalid consent links without sending a decision", async () => {
    window.location.hash = "#expired-token";
    previewGitHubEvidenceConsent.mockRejectedValue({ response: { status: 404 } });
    render(<GitHubEvidenceConsent />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/expired or was already used/i);
    expect(respondToGitHubEvidenceConsent).not.toHaveBeenCalled();
  });
});

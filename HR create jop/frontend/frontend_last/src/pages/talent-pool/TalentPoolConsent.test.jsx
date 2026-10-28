import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TalentPoolConsent from "./TalentPoolConsent";
import { previewTalentPoolConsent, respondToTalentPoolConsent } from "../../services/talentPoolService";

vi.mock("../../services/talentPoolService", () => ({
  previewTalentPoolConsent: vi.fn(),
  respondToTalentPoolConsent: vi.fn(),
}));

afterEach(() => {
  cleanup();
  window.location.hash = "";
  vi.clearAllMocks();
});

describe("TalentPoolConsent", () => {
  it("requires the candidate to explicitly accept before recording consent", async () => {
    window.location.hash = "#one-time-token";
    previewTalentPoolConsent.mockResolvedValue({
      organization_name: "HERA Test Org",
      consent_text: "Use my profile for future opportunities for 12 months.",
      consent_version: "test-v1",
      link_expires_at: "2026-11-01T00:00:00Z",
    });
    respondToTalentPoolConsent.mockResolvedValue({ decision: "accepted" });
    const user = userEvent.setup();
    render(<TalentPoolConsent />);

    expect(await screen.findByText(/Use my profile for future opportunities/)).toBeInTheDocument();
    expect(respondToTalentPoolConsent).not.toHaveBeenCalled();
    const acceptButton = screen.getByRole("button", { name: /I agree/i });
    expect(acceptButton).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /I am the candidate/i }));
    await user.click(acceptButton);

    expect(respondToTalentPoolConsent).toHaveBeenCalledWith("one-time-token", "accepted");
    expect(await screen.findByRole("status")).toHaveTextContent(/recorded for 12 months/i);
  });

  it("records a candidate decline as a separate choice", async () => {
    window.location.hash = "#decline-token";
    previewTalentPoolConsent.mockResolvedValue({
      organization_name: "HERA Test Org",
      consent_text: "Consent text.",
      consent_version: "test-v1",
      link_expires_at: "2026-11-01T00:00:00Z",
    });
    respondToTalentPoolConsent.mockResolvedValue({ decision: "declined" });
    const user = userEvent.setup();
    render(<TalentPoolConsent />);

    const declineButton = await screen.findByRole("button", { name: /Decline/i });
    await user.click(screen.getByRole("checkbox", { name: /I am the candidate/i }));
    await user.click(declineButton);

    expect(respondToTalentPoolConsent).toHaveBeenCalledWith("decline-token", "declined");
    expect(await screen.findByRole("status")).toHaveTextContent(/original application decision is unchanged/i);
  });

  it("shows a truthful invalid or expired link state", async () => {
    window.location.hash = "#expired-token";
    previewTalentPoolConsent.mockRejectedValue({ response: { status: 404 } });
    render(<TalentPoolConsent />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/expired or has already been used/i);
    expect(respondToTalentPoolConsent).not.toHaveBeenCalled();
  });
});

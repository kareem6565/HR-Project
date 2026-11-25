import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import LinkedInSourcing from "./LinkedInSourcing";
import {
  searchLinkedInCandidates,
  enrichSourcingCandidate,
  getOutreachDraft,
  personalizeOutreachDraft,
} from "../../services/sourcingService";

vi.mock("../../services/jobService", () => ({
  getJobs: vi.fn().mockResolvedValue([{ id: "j1", title: "Backend Engineer" }]),
}));
vi.mock("../../services/sourcingService", () => ({
  searchLinkedInCandidates: vi.fn().mockResolvedValue({ status: "unavailable", candidates: [] }),
  enrichSourcingCandidate: vi.fn(),
  getOutreachDraft: vi.fn(),
  personalizeOutreachDraft: vi.fn(),
}));

describe("LinkedInSourcing", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the sourcing hero and form", async () => {
    await act(async () => {
      render(<LinkedInSourcing />);
    });
    expect(screen.getByRole("heading", { name: /Tell HERA who you need/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Who do you need?")).toBeInTheDocument();
    expect(screen.getByText(/Your candidate suggestions appear here/i)).toBeInTheDocument();
  });

  it("requires a description or a job before searching", async () => {
    await act(async () => {
      render(<LinkedInSourcing />);
    });
    fireEvent.click(screen.getByRole("button", { name: /Find candidates/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Describe who you need/i);
  });

  it("shows the searching theater, then the honest empty state", async () => {
    await act(async () => {
      render(<LinkedInSourcing />);
    });
    fireEvent.change(screen.getByLabelText("Who do you need?"), {
      target: { value: "Senior backend engineer, Python" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Find candidates/i }));
    expect(screen.getByRole("status")).toHaveTextContent(/Reading your requirements/i);

    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.getByText(/LinkedIn sourcing is not enabled yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Looking for: Senior backend engineer, Python/i)).toBeInTheDocument();
  });


  it("finds an email for a suggested candidate on demand", async () => {
    searchLinkedInCandidates.mockResolvedValueOnce({
      status: "ok",
      searchId: "s1",
      candidates: [
        { id: "c1", name: "Ahmed Taha", headline: "Backend Engineer", profileUrl: "https://www.linkedin.com/in/ahmed-taha1", email: "" },
      ],
    });
    enrichSourcingCandidate.mockResolvedValueOnce({
      id: "c1",
      name: "Ahmed Taha",
      email: "ahmed.taha@bosta.co",
    });
    await act(async () => {
      render(<LinkedInSourcing />);
    });
    fireEvent.change(screen.getByLabelText("Who do you need?"), {
      target: { value: "backend engineer" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Find candidates/i }));
    await act(async () => {
      await Promise.resolve();
    });
    const findButton = screen.getByRole("button", { name: /Find email/i });
    fireEvent.click(findButton);
    await act(async () => {
      await Promise.resolve();
    });
    expect(enrichSourcingCandidate).toHaveBeenCalledWith("c1");
    expect(screen.getByRole("link", { name: "ahmed.taha@bosta.co" })).toHaveAttribute(
      "href",
      "mailto:ahmed.taha@bosta.co"
    );
  });


  it("opens an editable draft, personalizes it, and sends via mailto", async () => {
    searchLinkedInCandidates.mockResolvedValueOnce({
      status: "ok",
      searchId: "s1",
      candidates: [
        { id: "c1", name: "Ahmed Taha", headline: "Backend Engineer", email: "ahmed@example.com", profileUrl: "" },
      ],
    });
    getOutreachDraft.mockResolvedValueOnce({
      candidate_id: "c1",
      to: "ahmed@example.com",
      subject: "Senior Backend Engineer at Acme - interested?",
      body: "Hi Ahmed,\n\nTemplate body.",
      personalized: false,
    });
    personalizeOutreachDraft.mockResolvedValueOnce({
      candidate_id: "c1",
      to: "ahmed@example.com",
      subject: "Your Bosta work caught my eye",
      body: "Hi Ahmed, loved your backend work.",
      personalized: true,
    });
    await act(async () => {
      render(<LinkedInSourcing />);
    });
    fireEvent.change(screen.getByLabelText("Who do you need?"), {
      target: { value: "backend engineer" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Find candidates/i }));
    await act(async () => {
      await Promise.resolve();
    });
    fireEvent.click(screen.getByRole("button", { name: /Draft outreach/i }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByLabelText("Subject")).toHaveValue(
      "Senior Backend Engineer at Acme - interested?"
    );

    fireEvent.click(screen.getByRole("button", { name: /AI personalize/i }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByLabelText("Subject")).toHaveValue("Your Bosta work caught my eye");
    expect(screen.getByText(/Personalized by HERA/i)).toBeInTheDocument();

    const send = screen.getByRole("link", { name: /Open in email/i });
    expect(send.getAttribute("href")).toContain("mailto:ahmed@example.com");
    expect(send.getAttribute("href")).toContain("subject=Your%20Bosta%20work%20caught%20my%20eye");
  });
});

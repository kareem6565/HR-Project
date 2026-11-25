import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import LinkedInSourcing from "./LinkedInSourcing";

vi.mock("../../services/jobService", () => ({
  getJobs: vi.fn().mockResolvedValue([{ id: "j1", title: "Backend Engineer" }]),
}));
vi.mock("../../services/sourcingService", () => ({
  searchLinkedInCandidates: vi.fn().mockResolvedValue({ status: "unavailable", candidates: [] }),
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
});

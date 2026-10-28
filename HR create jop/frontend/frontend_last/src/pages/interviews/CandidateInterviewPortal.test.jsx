import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import CandidateInterviewPortal from "./CandidateInterviewPortal";
import {
  bookCandidateInterview,
  getCandidateInterviewMonth,
  getCandidateInterviewPreview,
} from "../../services/candidateInterviewPortalService";

vi.mock("../../services/candidateInterviewPortalService", () => ({
  bookCandidateInterview: vi.fn(),
  getCandidateInterviewMonth: vi.fn(),
  getCandidateInterviewPreview: vi.fn(),
}));

function renderPortal(token = "candidate-token-for-test-only") {
  window.location.hash = token ? `#${token}` : "";
  return render(<MemoryRouter><CandidateInterviewPortal /></MemoryRouter>);
}

beforeEach(() => {
  vi.clearAllMocks();
  getCandidateInterviewPreview.mockResolvedValue({
    status: "pending",
    job_title: "Backend Engineer",
    department: "Engineering",
  });
  getCandidateInterviewMonth.mockResolvedValue([]);
});

describe("CandidateInterviewPortal", () => {
  it("renders every date in the current month and explains that empty dates were not published", async () => {
    renderPortal();
    const grid = await screen.findByRole("group", { name: /Days in/i });
    const today = new Date();
    const dayCount = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
    expect(grid.querySelectorAll("button")).toHaveLength(dayCount);
    expect(await screen.findByText(/No interview times have been published for this month yet/i)).toBeInTheDocument();
    expect(getCandidateInterviewMonth).toHaveBeenCalledWith(
      "candidate-token-for-test-only",
      expect.stringMatching(/^\d{4}-\d{2}-01$/),
    );
  });

  it("books only the selected published slot and then locks the invitation", async () => {
    const user = userEvent.setup();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const date = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, "0")}-${String(tomorrow.getDate()).padStart(2, "0")}`;
    getCandidateInterviewMonth.mockResolvedValue([{
      availability_id: "availability-1",
      date,
      start_time: "10:00",
      end_time: "11:00",
      timezone: "Africa/Cairo",
      interviewer_name: "Grace Hopper",
    }]);
    bookCandidateInterview.mockResolvedValue({
      status: "scheduled",
      scheduled_date: date,
      scheduled_time: "10:00",
      scheduled_duration_minutes: 60,
      timezone: "Africa/Cairo",
    });
    renderPortal();

    const dateLabel = tomorrow.toLocaleDateString(undefined, {
      weekday: "long", month: "long", day: "numeric", year: "numeric",
    });
    await user.click(await screen.findByRole("button", { name: new RegExp(dateLabel) }));
    await user.click(await screen.findByRole("button", { name: /10:00–11:00/i }));
    await user.click(screen.getByRole("button", { name: "Confirm this time" }));

    expect(await screen.findByText(/Your interview is scheduled/i)).toBeInTheDocument();
    await waitFor(() => expect(bookCandidateInterview).toHaveBeenCalledWith({
      token: "candidate-token-for-test-only",
      availabilityId: "availability-1",
      scheduledTime: "10:00",
    }));
    expect(screen.getByText(/contact the recruiter/i)).toBeInTheDocument();
  });

  it("shows a truthful invalid-link state without requesting data", async () => {
    renderPortal("");
    expect(await screen.findByRole("heading", { name: "We couldn’t open this link" })).toBeInTheDocument();
    expect(getCandidateInterviewPreview).not.toHaveBeenCalled();
  });

  it("distinguishes an availability request failure from a month with no published times", async () => {
    getCandidateInterviewMonth.mockRejectedValueOnce(new Error("temporary server error"));
    renderPortal();

    expect(await screen.findByRole("alert")).toHaveTextContent(/Could not load this month’s available times/i);
    expect(screen.queryByText(/No interview times have been published/i)).not.toBeInTheDocument();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import InterviewsList, { countInterviewsScheduledThisWeek, getInterviewWeekDays } from "./InterviewsList";
import { getInterviews } from "../../services/interviewService";

vi.mock("../../services/interviewService", () => ({
  getInterviews: vi.fn(),
  cancelInterview: vi.fn(),
}));

function RouteProbe() {
  const location = useLocation();
  return <p>Current route: {location.pathname}</p>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/interviews"]}>
      <Routes>
        <Route path="/interviews" element={<InterviewsList />} />
        <Route path="/interviews/schedule" element={<RouteProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Interviews empty states", () => {
  it("explains a genuinely empty interview list and links to scheduling", async () => {
    getInterviews.mockResolvedValue([]);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText(/No interviews scheduled yet/i)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /Schedule interview/i }).at(-1));
    expect(screen.getByText("Current route: /interviews/schedule")).toBeInTheDocument();
  });

  it("shows only real interviews in the selected calendar week and preserves the list view", async () => {
    const today = new Date();
    const date = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, "0"), String(today.getDate()).padStart(2, "0")].join("-");
    const scheduled = {
      id: "interview-1",
      candidateName: "Ada Lovelace",
      job: "Engineer",
      type: "Technical",
      date,
      time: "10:00 AM",
      interviewers: [],
      status: "Scheduled",
    };
    getInterviews.mockResolvedValue([scheduled]);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("Engineer")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next week" }));
    expect(await screen.findByText(/No scheduled interviews this week/i)).toBeInTheDocument();
    expect(screen.getByText(/outside the selected week/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Today" }));
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "List" }));
    expect(screen.getByRole("columnheader", { name: "Candidate" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Interviewers" })).toBeInTheDocument();
  });

  it("builds a Monday-to-Sunday calendar week from a local date", () => {
    const days = getInterviewWeekDays(new Date(2026, 9, 23, 12));
    expect(days).toHaveLength(7);
    expect(days[0].getDay()).toBe(1);
    expect(days[6].getDay()).toBe(0);
    expect(days[0].getDate()).toBe(19);
    expect(days[6].getDate()).toBe(25);
  });

  it("distinguishes an empty status tab when interviews exist in another state", async () => {
    const scheduled = {
      id: "interview-1",
      candidateName: "Ada Lovelace",
      job: "Engineer",
      type: "Technical",
      date: "2026-11-01",
      time: "10:00 AM",
      interviewers: [],
      status: "Scheduled",
    };
    getInterviews.mockImplementation((status) =>
      Promise.resolve(status === "Completed" ? [] : [scheduled])
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Completed" }));
    await waitFor(() => expect(getInterviews).toHaveBeenLastCalledWith("Completed"));
    expect(await screen.findByText(/No completed interviews found/i)).toBeInTheDocument();
    expect(screen.getByText(/Try another interview status/i)).toBeInTheDocument();
  });
});

describe("interviews scheduled this week", () => {
  it("counts non-cancelled interview dates in the current Monday-to-Sunday week", () => {
    const friday = new Date(2026, 9, 23, 12);
    const interviews = [
      { status: "Scheduled", date: "2026-10-19" }, // Monday, inclusive
      { status: "Completed", date: "2026-10-25" }, // Sunday, inclusive
      { status: "Cancelled", date: "2026-10-21" },
      { status: "Scheduled", date: "2026-10-18" }, // Previous Sunday
      { status: "Scheduled", date: "2026-10-26" }, // Next Monday
      { status: "Scheduled", date: "not-a-date" },
    ];

    expect(countInterviewsScheduledThisWeek(interviews, friday)).toBe(2);
  });

  it("returns zero for an empty list", () => {
    expect(countInterviewsScheduledThisWeek([], new Date(2026, 9, 23))).toBe(0);
  });
});

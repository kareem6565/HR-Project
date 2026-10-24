import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ScheduleInterview from "./ScheduleInterview";
import { getInterviewers, getInterviewSlots, scheduleInterview } from "../../services/interviewService";
import { getCandidates } from "../../services/candidateService";
import { getJobs } from "../../services/jobService";
import { listQuestionSets } from "../../services/interviewQuestionSetService";

vi.mock("../../services/interviewService", () => ({
  getInterviewers: vi.fn(),
  getInterviewSlots: vi.fn(),
  scheduleInterview: vi.fn(),
}));

vi.mock("../../services/candidateService", () => ({ getCandidates: vi.fn() }));
vi.mock("../../services/jobService", () => ({ getJobs: vi.fn() }));
vi.mock("../../services/interviewQuestionSetService", () => ({ listQuestionSets: vi.fn() }));

function RouteProbe() {
  const location = useLocation();
  return <p>Current route: {location.pathname}</p>;
}

function renderPage(initialEntry = "/interviews/schedule") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/interviews/schedule" element={<ScheduleInterview />} />
        <Route path="/interviews" element={<RouteProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

async function chooseRequiredDetails(user) {
  await screen.findByRole("heading", { name: "Interview details" });
  await user.selectOptions(screen.getByLabelText("Candidate"), "candidate-1");
  await user.selectOptions(screen.getByLabelText("Interviewer"), "interviewer-1");
  await user.click(within(screen.getByRole("group", { name: "Interview date" })).getAllByRole("button")[0]);
}

beforeEach(() => {
  getCandidates.mockResolvedValue([
    { id: "candidate-1", name: "Ada Lovelace", title: "Engineer", jobId: "job-1" },
  ]);
  getJobs.mockResolvedValue([{ id: "job-1", title: "Software Engineer" }]);
  getInterviewers.mockResolvedValue([{ id: "interviewer-1", name: "Grace Hopper" }]);
  getInterviewSlots.mockResolvedValue({ occupied: [] });
  scheduleInterview.mockResolvedValue({ id: "interview-1" });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ScheduleInterview", () => {
  it("groups the form into clear steps and summarizes the appointment", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Plan an interview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Interview details" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Choose a date and time" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Appointment summary" })).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "Interview date" })).getAllByRole("button")).toHaveLength(4);
    expect(screen.getByText("Showing the next four weekdays. Times use your local timezone.")).toBeInTheDocument();
  });

  it("loads availability for the chosen day and disables a conflicting time", async () => {
    getInterviewSlots.mockResolvedValue({ occupied: [{ startMinutes: 600, endMinutes: 660 }] });
    const user = userEvent.setup();
    renderPage();
    await chooseRequiredDetails(user);

    await waitFor(() => expect(getInterviewSlots).toHaveBeenCalledWith(expect.any(String), "interviewer-1"));
    expect(await screen.findByText(/occupied window for this interviewer/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /10:00 AM/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /11:00 AM/ })).not.toBeDisabled();
  });

  it("submits the selected appointment and offers a route back to interviews", async () => {
    const user = userEvent.setup();
    renderPage();
    await chooseRequiredDetails(user);
    await user.click(screen.getByRole("button", { name: /10:00 AM/ }));
    await user.click(screen.getByRole("button", { name: "Confirm & schedule" }));

    await waitFor(() => expect(scheduleInterview).toHaveBeenCalledWith({
      candidate: expect.objectContaining({ id: "candidate-1" }),
      job: expect.objectContaining({ id: "job-1" }),
      interviewer: "interviewer-1",
      date: expect.any(String),
      time: "10:00 AM",
      durationMinutes: 60,
      questionSetId: null,
    }));
    expect(await screen.findByRole("heading", { name: "Interview Scheduled" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to Interviews" }));
    expect(screen.getByText("Current route: /interviews")).toBeInTheDocument();
  });

  it("reports availability and scheduling failures without implying success", async () => {
    getInterviewSlots.mockRejectedValue(new Error("network down"));
    const user = userEvent.setup();
    renderPage();
    await chooseRequiredDetails(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load availability for this day.");
    getInterviewSlots.mockResolvedValue({ occupied: [] });
    await user.click(within(screen.getByRole("group", { name: "Interview date" })).getAllByRole("button")[1]);
    await waitFor(() => expect(getInterviewSlots).toHaveBeenCalledTimes(2));
    await user.click(screen.getByRole("button", { name: /10:00 AM/ }));
    scheduleInterview.mockRejectedValueOnce({ response: { data: { detail: "Interview conflicts with an existing booking." } } });
    await user.click(screen.getByRole("button", { name: "Confirm & schedule" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Interview conflicts with an existing booking.");
    expect(screen.queryByRole("heading", { name: "Interview Scheduled" })).not.toBeInTheDocument();
  });

  it("shows honest empty guidance when no scheduling records are available", async () => {
    getCandidates.mockResolvedValue([]);
    getJobs.mockResolvedValue([]);
    getInterviewers.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/Add one through Screening first/i)).toBeInTheDocument();
    expect(screen.getByText(/Create a job before scheduling its interview/i)).toBeInTheDocument();
    expect(screen.getByText(/No interviewers are available for this workspace/i)).toBeInTheDocument();
    expect(scheduleInterview).not.toHaveBeenCalled();
    expect(listQuestionSets).not.toHaveBeenCalled();
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import InterviewAvailability from "./InterviewAvailability";
import {
  getInterviewers,
  getPublishedAvailability,
  publishInterviewAvailability,
} from "../../services/interviewService";

vi.mock("../../services/interviewService", () => ({
  getInterviewers: vi.fn(),
  getPublishedAvailability: vi.fn(),
  publishInterviewAvailability: vi.fn(),
  withdrawInterviewAvailability: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  getInterviewers.mockResolvedValue([{ id: "person-1", name: "Grace Hopper" }]);
  getPublishedAvailability.mockResolvedValue([]);
  publishInterviewAvailability.mockResolvedValue({ id: "availability-1" });
});

describe("InterviewAvailability", () => {
  it("renders all days in the month so HR chooses the dates that are truly free", async () => {
    render(<MemoryRouter><InterviewAvailability /></MemoryRouter>);
    const grid = await screen.findByRole("group", { name: /Choose an availability date/i });
    const today = new Date();
    const dayCount = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
    expect(grid.querySelectorAll("button")).toHaveLength(dayCount);
    expect(screen.getByText(/Only the dates and times you publish here/i)).toBeInTheDocument();
    expect(screen.getByText(/HERA does not read external calendars/i)).toBeInTheDocument();
  });

  it("publishes a dated window with HR-selected interviewer, duration, and time zone", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><InterviewAvailability /></MemoryRouter>);
    await screen.findByRole("heading", { name: "Manage interview availability" });
    const today = new Date();
    const target = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
    const accessibleDate = target.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    await user.click(screen.getByRole("button", { name: new RegExp(accessibleDate) }));
    await user.type(screen.getByLabelText("Start time"), "09:00");
    await user.type(screen.getByLabelText("End time"), "12:00");
    await user.selectOptions(screen.getByLabelText("Interview length"), "60");
    await user.click(screen.getByRole("button", { name: "Publish availability" }));

    await waitFor(() => expect(publishInterviewAvailability).toHaveBeenCalledWith(expect.objectContaining({
      interviewerUserId: "person-1",
      date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      startTime: "09:00",
      endTime: "12:00",
      durationMinutes: 60,
      timezone: expect.any(String),
    })));
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import {
  bookCandidateInterview,
  getCandidateInterviewMonth,
  getCandidateInterviewPreview,
} from "./candidateInterviewPortalService";

vi.mock("axios", () => ({ default: { post: vi.fn() } }));

describe("candidateInterviewPortalService", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sends the capability token in request bodies, never the URL or auth headers", async () => {
    axios.post.mockResolvedValue({ data: { status: "pending" } });
    await getCandidateInterviewPreview("unshared-test-token");
    await getCandidateInterviewMonth("unshared-test-token", "2026-11-01");
    await bookCandidateInterview({
      token: "unshared-test-token",
      availabilityId: "availability-1",
      scheduledTime: "10:00",
    });

    expect(axios.post).toHaveBeenNthCalledWith(
      1,
      "/api/v1/candidate-portal/interview/preview",
      { token: "unshared-test-token" },
      { headers: { "Content-Type": "application/json" } },
    );
    expect(axios.post).toHaveBeenNthCalledWith(
      2,
      "/api/v1/candidate-portal/interview/slots",
      { token: "unshared-test-token", month: "2026-11-01" },
      { headers: { "Content-Type": "application/json" } },
    );
    expect(axios.post.mock.calls[2][0]).not.toContain("unshared-test-token");
    expect(axios.post.mock.calls[2][1]).toEqual({
      token: "unshared-test-token",
      availability_id: "availability-1",
      scheduled_time: "10:00",
    });
    expect(axios.post.mock.calls[2][2].headers).not.toHaveProperty("Authorization");
  });
});

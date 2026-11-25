import { vi, describe, it, expect, beforeEach } from "vitest";
import apiClient from "./apiClient";
import { searchLinkedInCandidates, startSourcingSearch } from "./sourcingService";

vi.mock("./apiClient", () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

const SEARCH_ID = "11111111-1111-1111-1111-111111111111";

function searchPayload(overrides = {}) {
  return {
    id: SEARCH_ID,
    job_id: null,
    query_text: "backend engineer",
    status: "queued",
    error_code: null,
    error_message: null,
    candidates: [],
    ...overrides,
  };
}

describe("sourcingService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts a search with the plain-language query and optional job", async () => {
    apiClient.post.mockResolvedValue({ data: searchPayload() });
    const search = await startSourcingSearch({ jobId: "j1", needs: "backend engineer" });
    expect(apiClient.post).toHaveBeenCalledWith("/sourcing/searches", {
      query_text: "backend engineer",
      job_id: "j1",
    });
    expect(search.id).toBe(SEARCH_ID);
    expect(search.status).toBe("queued");
  });

  it("polls until the search succeeds and normalizes candidates", async () => {
    apiClient.post.mockResolvedValue({ data: searchPayload({ status: "running" }) });
    apiClient.get.mockResolvedValue({
      data: searchPayload({
        status: "succeeded",
        candidates: [
          {
            id: "c1",
            full_name: "Omar Example",
            headline: "Senior Backend Engineer",
            location: "Cairo, Egypt",
            current_title: "Backend Engineer",
            current_company: "Example Co",
            profile_url: "https://www.linkedin.com/in/omar-example/",
            fit_score: null,
            status: "suggested",
          },
        ],
      }),
    });

    const result = await searchLinkedInCandidates(
      { jobId: "", needs: "backend engineer" },
      { pollIntervalMs: 0 }
    );
    expect(result.status).toBe("ok");
    expect(result.searchId).toBe(SEARCH_ID);
    expect(result.candidates).toHaveLength(1);
    expect(result.candidates[0]).toMatchObject({
      name: "Omar Example",
      currentCompany: "Example Co",
      profileUrl: "https://www.linkedin.com/in/omar-example/",
    });
  });

  it("resolves unavailable when the backend has sourcing disabled", async () => {
    apiClient.post.mockRejectedValue({ response: { status: 503 } });
    const result = await searchLinkedInCandidates({ jobId: "", needs: "anything" });
    expect(result).toEqual({ status: "unavailable", candidates: [] });
  });

  it("surfaces the provider error message when the search fails", async () => {
    apiClient.post.mockResolvedValue({
      data: searchPayload({ status: "failed", error_message: "No external profiles matched." }),
    });
    const result = await searchLinkedInCandidates(
      { jobId: "", needs: "anything" },
      { pollIntervalMs: 0 }
    );
    expect(result.status).toBe("failed");
    expect(result.errorMessage).toBe("No external profiles matched.");
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});

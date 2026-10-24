import { describe, it, expect, vi, beforeEach } from "vitest";
import apiClient from "./apiClient";
import { uploadResume } from "./resumeService";

describe("resumeService multipart upload", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("constructs FormData with the uploaded file and posts to upload endpoint", async () => {
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
      data: { id: "res-123", original_filename: "cv.pdf" },
    });

    const file = new File(["dummy pdf content"], "cv.pdf", { type: "application/pdf" });
    const result = await uploadResume("cand-456", file);

    expect(postSpy).toHaveBeenCalledTimes(1);
    const [endpoint, formData] = postSpy.mock.calls[0];

    expect(endpoint).toBe("/candidates/cand-456/resumes/upload");
    expect(formData instanceof FormData).toBe(true);
    expect(formData.get("file")).toBeDefined();
    expect(result.id).toBe("res-123");
  });
});

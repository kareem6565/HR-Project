import { describe, expect, it } from "vitest";
import { JobApplicationStatus } from "../types/api";
import { getApplicationStatusGroup } from "./applicationStatus";

describe("application status groups", () => {
  it("keeps processing statuses separate from HR decision-mirrored states", () => {
    expect(getApplicationStatusGroup(JobApplicationStatus.ANALYZING).id).toBe("processing");
    expect(getApplicationStatusGroup(JobApplicationStatus.READY_FOR_REVIEW).id).toBe("processing");
    expect(getApplicationStatusGroup(JobApplicationStatus.HOLD).id).toBe("decision");
    expect(getApplicationStatusGroup(JobApplicationStatus.ADVANCED).id).toBe("decision");
    expect(getApplicationStatusGroup(JobApplicationStatus.REJECTED).id).toBe("decision");
  });

  it("keeps archived and unknown statuses out of processing and decision groups", () => {
    expect(getApplicationStatusGroup(JobApplicationStatus.ARCHIVED).id).toBe("other");
    expect(getApplicationStatusGroup("future_backend_state")).toBeNull();
  });
});

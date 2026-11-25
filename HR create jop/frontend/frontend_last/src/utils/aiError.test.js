import { describe, expect, it } from "vitest";
import { getAIErrorMessage } from "./aiError";

describe("getAIErrorMessage", () => {
  it("shows a clear budget reason and request reference", () => {
    const message = getAIErrorMessage({
      response: {
        data: {
          error_code: "app_test_budget_exceeded",
          detail: "The approved AI test budget would be exceeded.",
          request_id: "req-123",
        },
      },
    });

    expect(message).toContain("approved AI test budget");
    expect(message).toContain("Request ID: req-123");
  });

  it("uses API detail for new diagnostic codes", () => {
    expect(
      getAIErrorMessage({
        response: {
          data: {
            error_code: "provider_pricing_unavailable",
            detail: "The model price could not be checked. No request was sent.",
          },
        },
      })
    ).toBe("The model price could not be checked. No request was sent.");
  });
});

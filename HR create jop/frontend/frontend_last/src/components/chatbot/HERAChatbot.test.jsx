import { describe, expect, it } from "vitest";
import { linksFromResults } from "./HERAChatbot";

describe("HERA assistant navigation links", () => {
  it("does not expose the technical AI Activity page from chat results", () => {
    expect(
      linksFromResults([{ tool: "get_ai_activity", ok: true, data: { total_runs_24h: 2 } }]),
    ).toEqual([]);
  });

  it("keeps supported recruiting workflow links", () => {
    expect(linksFromResults([{ tool: "list_jobs", ok: true, data: {} }])).toEqual([
      { label: "View Jobs", to: "/jobs" },
    ]);
  });
});

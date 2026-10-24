import { describe, expect, it } from "vitest";
import { formatScore, parseScore } from "./score";

describe("score display values", () => {
  it.each([
    ["81.579", 81.579],
    ["8.1579e1", 81.579],
    ["0e0", 0],
    [100, 100],
  ])("parses %s within the backend score scale", (value, expected) => {
    expect(parseScore(value)).toBe(expected);
  });

  it.each([null, undefined, "", "  ", "NaN", "Infinity", "0x10", "-0.1", "100.01", "1e309"])(
    "rejects invalid score %s",
    (value) => expect(parseScore(value)).toBeNull(),
  );

  it("formats without exposing raw precision or scientific notation", () => {
    expect(formatScore("81.579")).toBe("81.6%");
    expect(formatScore("1e-7")).toBe("0%");
    expect(formatScore("100.01")).toBe("—");
  });
});

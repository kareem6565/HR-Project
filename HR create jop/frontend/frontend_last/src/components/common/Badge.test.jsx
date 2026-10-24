import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Badge from "./Badge";

describe("application status badges", () => {
  it("shows failed processing as an error and ready-for-review as pending", () => {
    const { container } = render(
      <>
        <Badge status="analysis_failed" />
        <Badge status="ready_for_review" />
      </>,
    );

    expect(screen.getByText("Analysis Failed").closest(".badge")).toHaveClass("badge-red");
    expect(screen.getByText("Ready For Review").closest(".badge")).toHaveClass("badge-blue");
    expect(container.querySelector(".badge-green")).toBeNull();
  });
});

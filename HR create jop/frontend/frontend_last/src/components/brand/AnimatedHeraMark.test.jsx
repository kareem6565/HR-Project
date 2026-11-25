import React from "react";
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AnimatedHeraMark from "./AnimatedHeraMark";

describe("AnimatedHeraMark", () => {
  it("renders the R-with-smile mark with live animation hooks", () => {
    const { container } = render(<AnimatedHeraMark size={40} />);
    const svg = container.querySelector("svg.hera-mark-animated");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("role", "img");
    expect(container.querySelectorAll("circle.hm-eye")).toHaveLength(2);
    expect(container.querySelector("path.hm-smile animate")).toBeInTheDocument();
    expect(container.querySelector("circle.hm-scan")).toBeInTheDocument();
  });
});

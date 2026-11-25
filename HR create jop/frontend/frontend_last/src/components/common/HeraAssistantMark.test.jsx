import React from "react";
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import HeraAssistantMark from "./HeraAssistantMark";

describe("HeraAssistantMark", () => {
  it("renders the robot mark with live animation hooks", () => {
    const { container } = render(<HeraAssistantMark size={32} />);
    const svg = container.querySelector("svg.hera-assistant-animated");
    expect(svg).toBeInTheDocument();
    expect(container.querySelectorAll("circle.ha-eye")).toHaveLength(2);
    expect(container.querySelector("path.ha-smile animate")).toBeInTheDocument();
    expect(container.querySelector("circle.ha-ping")).toBeInTheDocument();
    expect(container.querySelector("g.ha-head")).toBeInTheDocument();
  });

  it("stays static when animated is false", () => {
    const { container } = render(<HeraAssistantMark size={32} animated={false} />);
    expect(container.querySelector("svg.hera-assistant-animated")).not.toBeInTheDocument();
  });
});

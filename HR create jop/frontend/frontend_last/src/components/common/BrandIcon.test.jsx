import React from "react";
import { render } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import BrandIcon from "./BrandIcon";

vi.mock("../../context/ThemeContext", () => ({
  useThemeMode: () => "light",
}));

describe("BrandIcon", () => {
  it("renders the animated HERA mark at navbar size", () => {
    const { container } = render(<BrandIcon />);
    expect(container.querySelector(".brand-image svg.hera-mark-animated")).toBeInTheDocument();
  });
});

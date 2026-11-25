import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import LandingPage from "./LandingPage";

// jsdom lacks IntersectionObserver; stub it so the reveal wiring mounts.
class IOStub {
  observe(el) { el.classList.add("lp-visible"); }
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("IntersectionObserver", IOStub);

describe("LandingPage", () => {
  it("renders hero, journey steps, features and footer", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Hiring that reads/);
    expect(screen.getByText("Drop the CVs in")).toBeInTheDocument();
    expect(screen.getByText("Source beyond your inbox")).toBeInTheDocument();
    expect(screen.getByText("Matching")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Sign in/i }).length).toBeGreaterThan(0);
  });

  it("keeps all eight journey steps visible", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );
    const steps = screen.getAllByText(/^0\d$/);
    expect(steps).toHaveLength(8);
  });
});

import { describe, it, expect } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import fs from "fs";
import path from "path";
import Badge from "./Badge";
import Button from "./Button";
import LoadingSpinner from "./LoadingSpinner";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";

describe("HERA UI-00: Design Tokens and Visual Foundation", () => {
  it("authoritative HERA token palette is defined in index.css", () => {
    const cssPath = path.resolve(__dirname, "../../index.css");
    const cssContent = fs.readFileSync(cssPath, "utf-8");

    // Palette tokens
    expect(cssContent).toContain("--hera-teal: #1B3A3A");
    expect(cssContent).toContain("--hera-teal-deep: #082A24");
    expect(cssContent).toContain("--hera-teal-light: #EBF2F1");
    expect(cssContent).toContain("--hera-cream: #F5EFE2");
    expect(cssContent).toContain("--hera-cream-subtle: #FAF7F2");
    expect(cssContent).toContain("--hera-surface: #FFFFFF");
    expect(cssContent).toContain("--hera-gold: #E9D98A");
    expect(cssContent).toContain("--hera-sky: #6FA8B8");
    expect(cssContent).toContain("--hera-border: #E2E5E3");
    expect(cssContent).toContain("--hera-muted: #66736F");

    // Evidence & Decision tokens
    expect(cssContent).toContain("--evidence-supported: #067647");
    expect(cssContent).toContain("--evidence-partial: #B54708");
    expect(cssContent).toContain("--evidence-none: #475467");
    expect(cssContent).toContain("--decision-reject: #B42318");

    // Theme aliases
    expect(cssContent).toContain("--color-primary: var(--hera-teal)");
    expect(cssContent).toContain("--sidebar-bg: var(--hera-teal-deep)");
  });

  it("Badge renders teal tone for Interview and Hired statuses", () => {
    const { container: interviewContainer } = render(<Badge status="Interview" />);
    expect(interviewContainer.querySelector(".badge-teal")).toBeTruthy();
    expect(screen.getByText("Interview")).toBeTruthy();

    const { container: hiredContainer } = render(<Badge status="Hired" />);
    expect(hiredContainer.querySelector(".badge-teal")).toBeTruthy();
    expect(screen.getByText("Hired")).toBeTruthy();
  });

  it("Button renders standard primary, secondary, and danger variants", () => {
    const { container, rerender } = render(<Button variant="primary">Submit</Button>);
    expect(container.querySelector(".btn-primary")).toBeTruthy();

    rerender(<Button variant="secondary">Cancel</Button>);
    expect(container.querySelector(".btn-secondary")).toBeTruthy();

    rerender(<Button variant="danger">Delete</Button>);
    expect(container.querySelector(".btn-danger")).toBeTruthy();
  });

  it("LoadingSpinner renders the spinner element", () => {
    const { container } = render(<LoadingSpinner label="Evaluating CVs..." />);
    expect(container.querySelector(".spinner")).toBeTruthy();
    expect(screen.getByText("Evaluating CVs...")).toBeTruthy();
  });

  it("EmptyState and ErrorState render accessible messages and actions", () => {
    render(<EmptyState message="No candidates in this stage." />);
    expect(screen.getByText("No candidates in this stage.")).toBeTruthy();

    let retried = false;
    render(<ErrorState message="Extraction failed." onRetry={() => { retried = true; }} />);
    expect(screen.getByText("Extraction failed.")).toBeTruthy();
    const retryBtn = screen.getByRole("button", { name: /try again/i });
    retryBtn.click();
    expect(retried).toBe(true);
  });
});

import { describe, it, expect, vi } from "vitest";
import React, { useState } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import fs from "fs";
import path from "path";
import Modal from "./Modal";
import DataTable from "./DataTable";
import LoadingSpinner from "./LoadingSpinner";
import ErrorState from "./ErrorState";
import PipelineActions from "./PipelineActions";

describe("HERA UI-01: Accessibility Basics and Interactive Controls", () => {
  it("focus styles, reduced motion, and skip-to-content rules exist in index.css", () => {
    const cssPath = path.resolve(__dirname, "../../index.css");
    const cssContent = fs.readFileSync(cssPath, "utf-8");

    // Visible focus rules
    expect(cssContent).toContain(":focus-visible");
    expect(cssContent).toContain("outline: 2px solid var(--hera-teal)");
    expect(cssContent).toContain("box-shadow: var(--focus-ring)");

    // Prefers reduced motion
    expect(cssContent).toContain("@media (prefers-reduced-motion: reduce)");
    expect(cssContent).toContain("animation: none !important");

    // Skip to content
    expect(cssContent).toContain(".skip-to-content");
    expect(cssContent).toContain(".skip-to-content:focus-visible");
  });

  describe("Modal Accessibility and Safe Dismiss", () => {
    it("renders with role=dialog, aria-modal, and accessible title label", () => {
      render(
        <Modal open={true} title="Decision Confirmation" onClose={vi.fn()}>
          <p>Please confirm your decision.</p>
        </Modal>
      );

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeTruthy();
      expect(dialog.getAttribute("aria-modal")).toBe("true");
      expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();

      const title = screen.getByText("Decision Confirmation");
      expect(title.getAttribute("id")).toBe(dialog.getAttribute("aria-labelledby"));

      const closeBtn = screen.getByRole("button", { name: /close dialog/i });
      expect(closeBtn).toBeTruthy();
    });

    it("triggers onClose on Escape key press", () => {
      const handleClose = vi.fn();
      render(
        <Modal open={true} title="Cancel Interview?" onClose={handleClose}>
          <p>Are you sure?</p>
        </Modal>
      );

      fireEvent.keyDown(window, { key: "Escape" });
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it("safe overlay dismiss: does not dismiss when form has unsaved text", () => {
      const handleClose = vi.fn();
      const { container } = render(
        <Modal open={true} title="Record Decision" onClose={handleClose}>
          <textarea placeholder="Reason" defaultValue="Candidate showed strong system design skills." />
        </Modal>
      );

      const overlay = container.querySelector(".modal-overlay");
      fireEvent.click(overlay);

      // Should NOT close because user typed into the textarea
      expect(handleClose).not.toHaveBeenCalled();
    });

    it("dismisses on overlay click when there is no unsaved input", () => {
      const handleClose = vi.fn();
      const { container } = render(
        <Modal open={true} title="Empty Modal" onClose={handleClose}>
          <p>Static informational message.</p>
        </Modal>
      );

      const overlay = container.querySelector(".modal-overlay");
      fireEvent.click(overlay);
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it("restores focus to previously active element on close", () => {
      const button = document.createElement("button");
      button.textContent = "Open Modal";
      document.body.appendChild(button);
      button.focus();
      expect(document.activeElement).toBe(button);

      const { unmount } = render(
        <Modal open={true} title="Focus Restoration Test" onClose={vi.fn()}>
          <button type="button">Action</button>
        </Modal>
      );

      unmount();
      expect(document.activeElement).toBe(button);
      document.body.removeChild(button);
    });
  });

  describe("DataTable Keyboard Interaction", () => {
    it("makes clickable rows focusable and operable with Enter and Space keys", () => {
      const handleRowClick = vi.fn();
      const columns = [{ key: "name", header: "Name" }];
      const data = [{ id: "1", name: "Alice Developer" }];

      const { container } = render(<DataTable columns={columns} data={data} onRowClick={handleRowClick} />);

      const row = container.querySelector("tr.clickable");
      expect(row).toBeTruthy();
      expect(row.getAttribute("tabindex")).toBe("0");

      fireEvent.keyDown(row, { key: "Enter" });
      expect(handleRowClick).toHaveBeenCalledWith(data[0]);

      fireEvent.keyDown(row, { key: " " });
      expect(handleRowClick).toHaveBeenCalledTimes(2);
    });
  });

  describe("Semantics for LoadingSpinner and ErrorState", () => {
    it("LoadingSpinner has role=status and aria-live=polite", () => {
      render(<LoadingSpinner label="Evaluating resume..." />);
      const statusEl = screen.getByRole("status");
      expect(statusEl.getAttribute("aria-live")).toBe("polite");
      expect(screen.getByText("Evaluating resume...")).toBeTruthy();
    });

    it("ErrorState has role=alert and aria-live=assertive", () => {
      render(<ErrorState message="Server connection failed." onRetry={vi.fn()} />);
      const alertEl = screen.getByRole("alert");
      expect(alertEl.getAttribute("aria-live")).toBe("assertive");
      expect(screen.getByText("Server connection failed.")).toBeTruthy();
    });
  });

  describe("PipelineActions Accessible Controls", () => {
    it("exposes accessible names on all actions even when sized small", () => {
      render(<PipelineActions currentStatus="advance" onDecision={vi.fn()} size="small" />);
      const group = screen.getByRole("group", { name: /pipeline decisions/i });
      expect(group).toBeTruthy();

      const advanceBtn = screen.getByRole("button", { name: "Advance" });
      const holdBtn = screen.getByRole("button", { name: "Hold" });
      const rejectBtn = screen.getByRole("button", { name: "Reject" });

      expect(advanceBtn.getAttribute("aria-pressed")).toBe("true");
      expect(holdBtn.getAttribute("aria-pressed")).toBe("false");
      expect(rejectBtn.getAttribute("aria-pressed")).toBe("false");
    });
  });
});

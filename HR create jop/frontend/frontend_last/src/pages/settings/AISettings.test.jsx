import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AISettings from "./AISettings";
import { ThemeProvider } from "../../context/ThemeContext";
import { MemoryRouter } from "react-router-dom";
import { getAISettings } from "../../services/aiSettingsService";

vi.mock("../../services/aiSettingsService", () => ({
  getAISettings: vi.fn().mockResolvedValue({
    provider: "ollama",
    model: "gemma4:31b",
    has_api_key: true,
    api_key_source: "environment",
  }),
  verifyApiKey: vi.fn(),
}));

describe("AI settings appearance", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => {
    cleanup();
    delete document.documentElement.dataset.theme;
  });

  it("removes the duplicated activity log and switches between persisted themes", async () => {
    render(
      <ThemeProvider>
        <MemoryRouter><AISettings /></MemoryRouter>
      </ThemeProvider>,
    );

    const darkButton = await screen.findByRole("button", { name: "Dark" });
    expect(screen.getByRole("heading", { name: "Theme" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open ai activity/i })).toHaveAttribute("href", "/ai-activity");
    expect(screen.queryByText("Workflow observability — not an AI agent. These are execution traces.")).not.toBeInTheDocument();

    fireEvent.click(darkButton);
    await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "dark"));
    expect(localStorage.getItem("hera-theme")).toBe("dark");
    expect(darkButton).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "Light" }));
    await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "light"));
    expect(localStorage.getItem("hera-theme")).toBe("light");
  });

  it("restores a previously selected dark theme", async () => {
    localStorage.setItem("hera-theme", "dark");
    render(
      <ThemeProvider>
        <MemoryRouter><AISettings /></MemoryRouter>
      </ThemeProvider>,
    );

    expect(await screen.findByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "dark"));
  });

  it("shows OpenRouter as the active provider and reports a missing key safely", async () => {
    vi.mocked(getAISettings).mockResolvedValueOnce({
      provider: "openrouter",
      model: "openai/gpt-4o-mini",
      has_api_key: false,
      api_key_source: "none",
    });

    render(
      <ThemeProvider>
        <MemoryRouter><AISettings /></MemoryRouter>
      </ThemeProvider>,
    );

    expect(await screen.findByText("openrouter")).toBeInTheDocument();
    expect(screen.getByText("openai/gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("Missing")).toBeInTheDocument();
    expect(screen.getByText(/manage the provider and its API key in the backend environment/i)).toBeInTheDocument();
  });
});

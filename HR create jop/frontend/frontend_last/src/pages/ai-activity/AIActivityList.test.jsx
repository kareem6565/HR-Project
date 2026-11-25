import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import AIActivityList from "./AIActivityList";

vi.mock("../../services/aiActivityService", () => ({
  getAIActivityRuns: vi.fn().mockResolvedValue([]),
  getAIActivityStats: vi.fn().mockResolvedValue({
    totalRuns24h: 1,
    successful: 0,
    failed: 1,
    avgLatency: "1.2s",
  }),
  getAIProviderRequests: vi.fn().mockResolvedValue([{
    id: "event-1",
    requestId: "app-req-123",
    providerRequestId: "or-req-456",
    provider: "openrouter",
    model: "deepseek/model",
    feature: "job_structuring",
    status: "error",
    errorCode: "provider_rate_limit",
    providerStatus: 429,
    inputTokens: 250,
    outputTokens: 0,
    duration: "1.2s",
    timestamp: "Nov 25 · 3:30 PM",
  }]),
  retryRun: vi.fn(),
}));

describe("AI provider request diagnostics", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("shows safe failure details and both correlation IDs", async () => {
    render(<AIActivityList />);

    expect(await screen.findByRole("heading", { name: "Recent AI provider requests" })).toBeInTheDocument();
    expect(screen.getByText(/provider_rate_limit/)).toBeInTheDocument();
    expect(screen.getByText("HTTP 429")).toBeInTheDocument();
    expect(screen.getByText("App: app-req-123")).toBeInTheDocument();
    expect(screen.getByText("Provider: or-req-456")).toBeInTheDocument();
    expect(screen.queryByText(/prompt|resume|candidate/i)).not.toBeInTheDocument();
  });
});

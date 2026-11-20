import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import JobDistributionPanel from "./JobDistributionPanel";
import {
  createJobDistribution,
  generateDistributionPost,
  listJobDistributions,
  markJobDistributionShared,
} from "../../services/jobDistributionService";

vi.mock("../../services/jobDistributionService", () => ({
  createJobDistribution: vi.fn(),
  generateDistributionPost: vi.fn(),
  listJobDistributions: vi.fn(),
  markJobDistributionShared: vi.fn(),
  updateJobDistribution: vi.fn(),
}));

const campaign = {
  id: "distribution-1",
  channel: "linkedin",
  campaign_name: "Engineer campaign",
  tracking_key: "a".repeat(32),
  post_text: "",
  status: "draft",
  ai_generated: false,
};

beforeEach(() => {
  listJobDistributions.mockResolvedValue([]);
  createJobDistribution.mockResolvedValue(campaign);
  generateDistributionPost.mockResolvedValue({ post_text: "A reviewed role draft.", ai_generated: true });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("JobDistributionPanel", () => {
  it("keeps sharing manual, requires HR review, and creates a tracked public link", async () => {
    render(<JobDistributionPanel job={{ id: "job-1", publicId: "public-job", title: "Engineer" }} />);

    fireEvent.click(await screen.findByRole("button", { name: "Create post draft" }));
    const post = await screen.findByRole("textbox", { name: "Recruitment post" });
    await waitFor(() => expect(post).toHaveValue("A reviewed role draft."));

    const trackedLink = screen.getByRole("link", { name: /careers\/public-job/ });
    const url = new URL(trackedLink.href);
    expect(url.searchParams.get("utm_source")).toBe("linkedin");
    expect(url.searchParams.get("utm_medium")).toBe("social");
    expect(url.searchParams.get("utm_campaign")).toBe("a".repeat(32));
    expect(screen.getByText(/AI draft based on the approved profile/i)).toBeInTheDocument();

    const copyButton = screen.getByRole("button", { name: "Copy post + link" });
    const sharedButton = screen.getByRole("button", { name: "Mark as shared" });
    expect(copyButton).toBeDisabled();
    expect(sharedButton).toBeDisabled();
    expect(markJobDistributionShared).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("checkbox", { name: /I reviewed this post/i }));
    expect(copyButton).toBeEnabled();
    expect(sharedButton).toBeEnabled();
    expect(markJobDistributionShared).not.toHaveBeenCalled();
  });
});

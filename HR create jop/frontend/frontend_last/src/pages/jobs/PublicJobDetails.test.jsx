import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PublicJobDetails from "./PublicJobDetails";
import { getPublicJob } from "../../services/jobService";

vi.mock("../../services/jobService", () => ({ getPublicJob: vi.fn() }));

function renderPage(path = "/careers/abc") {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/careers/:publicId" element={<PublicJobDetails />} />
  </Routes></MemoryRouter>);
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("PublicJobDetails", () => {
  it("renders public role details and the closed application state", async () => {
    getPublicJob.mockResolvedValue({
      title: "Product Designer", organization_name: "Public Company", location: "Cairo",
      job_type: "Full-time", work_mode: "hybrid", description: "Design useful products.",
      responsibilities: ["Create prototypes"], required_qualifications: ["Accessibility experience"],
      preferred_qualifications: ["Design systems"], publication_status: "closed", accepting_applications: false,
    });
    renderPage();
    expect(await screen.findByRole("heading", { name: "Product Designer" })).toBeInTheDocument();
    expect(screen.getByText("Public Company")).toBeInTheDocument();
    expect(screen.getByText("Applications are no longer being accepted for this job.")).toBeInTheDocument();
    expect(screen.getByText("Create prototypes")).toBeInTheDocument();
  });

  it("shows a public unavailable state for an invalid or unpublished link", async () => {
    getPublicJob.mockRejectedValue(new Error("not found"));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Job listing unavailable" })).toBeInTheDocument();
  });

  it("preserves campaign attribution through the apply link", async () => {
    getPublicJob.mockResolvedValue({
      title: "Product Designer", organization_name: "Public Company", accepting_applications: true,
    });
    renderPage("/careers/abc?utm_source=linkedin&utm_medium=social&utm_campaign=campaign-key");
    const applyLink = await screen.findByRole("link", { name: "Apply for this job" });
    expect(applyLink).toHaveAttribute(
      "href",
      "/careers/abc/apply?utm_source=linkedin&utm_medium=social&utm_campaign=campaign-key",
    );
    expect(getPublicJob).toHaveBeenCalledWith("abc", { utm_campaign: "campaign-key" });
  });
});

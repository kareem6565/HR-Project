import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PublicJobApplication from "./PublicJobApplication";

const api = vi.hoisted(() => ({
  getPublicJob: vi.fn(),
  getPublicApplicationConfig: vi.fn(),
  submitPublicApplication: vi.fn(),
}));
vi.mock("../../services/publicApi", () => api);

const job = {
  title: "Product Designer",
  organization_name: "HERA Demo",
  description: "Design useful products with a collaborative team.",
  accepting_applications: true,
};
const config = {
  notice_available: true,
  privacy_notice_text: "Test notice: use this information to process this application.",
  privacy_notice_version: "test-v1",
  turnstile_required: false,
  turnstile_server_configured: false,
  max_upload_bytes: 5 * 1024 * 1024,
};

function renderPage(path = "/careers/public-id/apply?utm_source=linkedin&utm_medium=social&utm_campaign=campaign-key") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/careers/:publicId/apply" element={<PublicJobApplication />} /></Routes>
    </MemoryRouter>,
  );
}

describe("PublicJobApplication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getPublicJob.mockResolvedValue(job);
    api.getPublicApplicationConfig.mockResolvedValue(config);
    api.submitPublicApplication.mockResolvedValue({ application_reference: "safe-reference" });
  });

  it("shows the selected job, fields, and configured notice", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Product Designer" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Full name/)).toBeInTheDocument();
    expect(screen.getByText(config.privacy_notice_text)).toBeInTheDocument();
    expect(screen.getByLabelText(/acknowledge this notice/)).toBeRequired();
  });

  it("submits the resume and privacy notice version, then shows only a safe reference", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Product Designer" });
    await user.type(screen.getByLabelText(/Full name/), "Alex Applicant");
    await user.type(screen.getByLabelText(/Email address/), "alex@example.com");
    const resumeInput = screen.getByLabelText(/Resume \/ CV/);
    await user.upload(resumeInput, new File(["%PDF"], "resume.pdf", { type: "application/pdf" }));
    expect(resumeInput.files).toHaveLength(1);
    await user.click(screen.getByLabelText(/acknowledge this notice/));
    const form = screen.getByRole("button", { name: "Submit application" }).closest("form");
    fireEvent.submit(form);
    await screen.findByText("safe-reference");
    const [publicId, formData] = api.submitPublicApplication.mock.calls[0];
    expect(publicId).toBe("public-id");
    expect(formData.get("privacy_notice_version")).toBe("test-v1");
    expect(formData.get("utm_source")).toBe("linkedin");
    expect(formData.get("utm_medium")).toBe("social");
    expect(formData.get("utm_campaign")).toBe("campaign-key");
    expect(formData.get("resume").name).toBe("resume.pdf");
    expect(screen.getByText("Your application has been received. HERA has queued your CV for processing.")).toBeInTheDocument();
  });

  it("fails closed when no approved notice is configured", async () => {
    api.getPublicApplicationConfig.mockResolvedValue({ ...config, notice_available: false });
    renderPage();
    expect(await screen.findByText(/privacy notice is configured/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Full name/)).not.toBeInTheDocument();
  });

  it("does not offer a form for a closed job", async () => {
    api.getPublicJob.mockResolvedValue({ ...job, accepting_applications: false });
    renderPage();
    expect(await screen.findByText(/no longer being accepted/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Full name/)).not.toBeInTheDocument();
  });
});

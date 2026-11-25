import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PipelineStagePanel from "./PipelineStagePanel";
import { correctHiredPipelineStage, getPipelineState, transitionPipelineStage } from "../../services/reviewService";

vi.mock("../../services/reviewService", () => ({
  getPipelineState: vi.fn(),
  transitionPipelineStage: vi.fn(),
  correctHiredPipelineStage: vi.fn(),
}));

const state = {
  application_id: "app-1",
  status: "ready_for_review",
  pipeline_stage: "review",
  allowed_next_stages: ["screening", "interview", "withdrawn", "archived"],
  allowed_correction_stages: [],
  reason_required_stages: ["screening", "withdrawn"],
  is_admin: false,
  transitions: [],
};

describe("PipelineStagePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getPipelineState.mockResolvedValue(state);
    transitionPipelineStage.mockResolvedValue({ ...state, pipeline_stage: "interview", allowed_next_stages: [] });
  });

  it("uses allowed transitions from the API and sends the expected stage", async () => {
    const user = userEvent.setup();
    render(<PipelineStagePanel applicationId="app-1" />);
    expect(await screen.findByText("HR review")).toBeInTheDocument();
    const select = screen.getByRole("combobox", { name: "Next pipeline stage" });
    expect([...select.options].map((option) => option.value)).toEqual(state.allowed_next_stages);
    await user.selectOptions(select, "interview");
    await user.click(screen.getByRole("button", { name: "Update stage" }));
    await waitFor(() => expect(transitionPipelineStage).toHaveBeenCalledWith("app-1", expect.objectContaining({
      expected_stage: "review", to_stage: "interview", idempotency_key: expect.any(String),
    })));
  });

  it("requires a reason code for withdrawn transitions", async () => {
    const user = userEvent.setup();
    render(<PipelineStagePanel applicationId="app-1" />);
    await screen.findByText("HR review");
    await user.selectOptions(screen.getByRole("combobox", { name: "Next pipeline stage" }), "withdrawn");
    expect(screen.getByRole("button", { name: "Update stage" })).toBeDisabled();
    await user.selectOptions(screen.getByRole("combobox", { name: "Reason code" }), "candidate_request");
    expect(screen.getByRole("button", { name: "Update stage" })).toBeEnabled();
  });

  it("shows an actionable error and retry path when the API fails", async () => {
    getPipelineState.mockRejectedValueOnce(new Error("network"));
    render(<PipelineStagePanel applicationId="app-1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Pipeline information could not be loaded.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(getPipelineState).toHaveBeenCalledTimes(2));
  });

  it("renders admin correction options supplied by the API and requires its reason", async () => {
    const user = userEvent.setup();
    getPipelineState.mockResolvedValueOnce({
      ...state, status: "advanced", pipeline_stage: "hired", allowed_next_stages: [],
      allowed_correction_stages: ["screening", "review"], reason_required_stages: [], is_admin: true,
    });
    correctHiredPipelineStage.mockResolvedValue({ ...state, pipeline_stage: "review" });
    render(<PipelineStagePanel applicationId="app-1" />);
    await screen.findByText("Hired");
    const select = screen.getByRole("combobox", { name: "Next pipeline stage" });
    expect([...select.options].map((option) => option.value)).toEqual(["screening", "review"]);
    expect(screen.getByRole("button", { name: "Record correction" })).toBeDisabled();
    await user.selectOptions(screen.getByRole("combobox", { name: "Reason code" }), "data_correction");
    await user.type(screen.getByRole("textbox", { name: "Required correction reason" }), "Wrong stage recorded");
    await user.click(screen.getByRole("button", { name: "Record correction" }));
    await waitFor(() => expect(correctHiredPipelineStage).toHaveBeenCalledWith("app-1", expect.objectContaining({
      expected_stage: "hired", to_stage: "screening", reason_code: "data_correction",
      reason: "Wrong stage recorded",
    })));
  });
});

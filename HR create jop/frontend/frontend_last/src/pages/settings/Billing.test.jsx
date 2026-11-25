import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Billing from "./Billing";
import { changePlan } from "../../services/billingService";

const { PLAN_ROWS, FREE_SUBSCRIPTION, PRO_SUBSCRIPTION, USAGE } = vi.hoisted(() => {
const PLAN_ROWS = [
  {
    id: "p1",
    code: "free",
    name: "Starter",
    description: "Try HERA.",
    price_monthly_cents: 0,
    currency: "USD",
    limits: { active_jobs: 3, screenings_per_month: 50, seats: 2 },
    features: { talent_pool: true, ocr_cv_intake: false },
    sort_order: 0,
  },
  {
    id: "p2",
    code: "pro",
    name: "Pro",
    description: "For growing teams.",
    price_monthly_cents: 4900,
    currency: "USD",
    limits: { active_jobs: 25, screenings_per_month: 1000, seats: 10 },
    features: { talent_pool: true, ocr_cv_intake: true },
    sort_order: 1,
  },
  {
    id: "p3",
    code: "business",
    name: "Business",
    description: "High-volume hiring.",
    price_monthly_cents: 19900,
    currency: "USD",
    limits: { active_jobs: -1, screenings_per_month: 10000, seats: -1 },
    features: { talent_pool: true, ocr_cv_intake: true, audit_exports: true },
    sort_order: 2,
  },
];

const FREE_SUBSCRIPTION = {
  id: "s1",
  organization_id: "o1",
  status: "active",
  provider: "none",
  current_period_start: null,
  current_period_end: null,
  cancel_at_period_end: false,
  plan: PLAN_ROWS[0],
};

const PRO_SUBSCRIPTION = { ...FREE_SUBSCRIPTION, provider: "manual", plan: PLAN_ROWS[1] };

const USAGE = {
  plan_code: "free",
  meters: [
    { meter: "active_jobs", used: 2, limit: 3, unlimited: false, percent_used: 66.7 },
    { meter: "screenings_per_month", used: 0, limit: 50, unlimited: false, percent_used: 0 },
    { meter: "seats", used: 1, limit: 2, unlimited: false, percent_used: 50 },
  ],
};

return { PLAN_ROWS, FREE_SUBSCRIPTION, PRO_SUBSCRIPTION, USAGE };
});

let mockIsAdmin = true;

vi.mock("../../hooks/useAuth", () => ({
  default: () => ({ isAdmin: mockIsAdmin }),
}));

vi.mock("../../services/billingService", () => ({
  getPlans: vi.fn().mockResolvedValue(PLAN_ROWS),
  getSubscription: vi.fn().mockResolvedValue(FREE_SUBSCRIPTION),
  getUsage: vi.fn().mockResolvedValue(USAGE),
  changePlan: vi.fn(),
}));

describe("Billing page", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    mockIsAdmin = true;
  });

  it("shows current plan, usage meters, and the full plan catalog", async () => {
    render(
      <MemoryRouter>
        <Billing />
      </MemoryRouter>
    );

    expect((await screen.findAllByText("Starter")).length).toBeGreaterThan(0);
    expect(screen.getByText("Billing & Plan")).toBeInTheDocument();
    expect(screen.getByText("No billing")).toBeInTheDocument();

    // Usage meters
    expect(screen.getByText("Active jobs")).toBeInTheDocument();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    expect(screen.getByText("Screenings this month")).toBeInTheDocument();
    expect(screen.getByText("Team seats")).toBeInTheDocument();

    // Catalog: prices, limits, and feature flags render
    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.getByText("$49/mo")).toBeInTheDocument();
    expect(screen.getByText("$199/mo")).toBeInTheDocument();
    expect(screen.getAllByText(/Unlimited active jobs/).length).toBe(1);
    expect(screen.getAllByText(/OCR CV intake/).length).toBeGreaterThan(0);

    // Current plan is marked and its button disabled
    const currentButton = screen.getByRole("button", { name: "Current plan" });
    expect(currentButton).toBeDisabled();
  });

  it("lets an admin upgrade and shows the manual-billing notice", async () => {
    vi.mocked(changePlan).mockResolvedValue({ subscription: PRO_SUBSCRIPTION, checkout: "manual" });

    render(
      <MemoryRouter>
        <Billing />
      </MemoryRouter>
    );

    const upgradeButtons = await screen.findAllByRole("button", { name: "Upgrade" });
    fireEvent.click(upgradeButtons[0]);

    await waitFor(() => expect(changePlan).toHaveBeenCalledWith("pro"));
    expect(
      await screen.findByText(/Plan updated to Pro/)
    ).toBeInTheDocument();
  });

  it("disables plan changes for non-admins", async () => {
    mockIsAdmin = false;

    render(
      <MemoryRouter>
        <Billing />
      </MemoryRouter>
    );

    const adminOnlyButtons = await screen.findAllByRole("button", { name: "Admin only" });
    expect(adminOnlyButtons.length).toBe(2);
    adminOnlyButtons.forEach((button) => expect(button).toBeDisabled());
    expect(screen.queryByRole("button", { name: "Upgrade" })).not.toBeInTheDocument();
  });
});

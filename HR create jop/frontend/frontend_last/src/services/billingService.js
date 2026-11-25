import apiClient from "./apiClient";

// Billing service. Contract: backend /api/v1/billing/* (docs/MONETIZATION.md).
// v1 runs in manual billing mode: plan changes activate immediately and are
// invoiced outside the product until a payment provider is integrated.

export async function getPlans() {
  const { data } = await apiClient.get("/billing/plans");
  return data;
}

export async function getSubscription() {
  const { data } = await apiClient.get("/billing/subscription");
  return data;
}

export async function changePlan(planCode) {
  const { data } = await apiClient.post("/billing/subscription/plan", {
    plan_code: planCode,
  });
  return data;
}

export async function getUsage() {
  const { data } = await apiClient.get("/billing/usage");
  return data;
}

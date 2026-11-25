from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    price_monthly_cents: int
    currency: str
    limits: dict[str, Any]
    features: dict[str, Any]
    sort_order: int


class SubscriptionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    status: str
    provider: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    plan: PlanResponse


class ChangePlanRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)


class ChangePlanResponse(BaseModel):
    subscription: SubscriptionResponse
    # Where a payment provider will attach: today "manual" (invoiced outside
    # the product); becomes a checkout/session URL once Stripe is integrated.
    checkout: str = "manual"


class UsageMeterResponse(BaseModel):
    meter: str
    used: int
    limit: int
    unlimited: bool
    percent_used: float | None


class UsageResponse(BaseModel):
    plan_code: str
    meters: list[UsageMeterResponse]

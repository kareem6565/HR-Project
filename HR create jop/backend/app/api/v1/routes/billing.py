from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context, require_roles
from app.api.v1.schemas.billing import (
    ChangePlanRequest,
    ChangePlanResponse,
    PlanResponse,
    SubscriptionResponse,
    UsageMeterResponse,
    UsageResponse,
)
from app.core.database import get_db
from app.models import OrganizationSubscription, Plan
from app.services.subscription_service import SubscriptionService

router = APIRouter()


def _plan_response(plan: Plan) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        price_monthly_cents=plan.price_monthly_cents,
        currency=plan.currency,
        limits=plan.limits,
        features=plan.features,
        sort_order=plan.sort_order,
    )


def _subscription_response(subscription: OrganizationSubscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=subscription.id,
        organization_id=subscription.organization_id,
        status=subscription.status,
        provider=subscription.provider,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        plan=_plan_response(subscription.plan),
    )


@router.get(
    "/billing/plans",
    response_model=list[PlanResponse],
)
def list_plans(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """List the active plan catalog (any authenticated org member)."""
    plans = SubscriptionService().list_plans(db)
    db.commit()
    return [_plan_response(plan) for plan in plans]


@router.get(
    "/billing/subscription",
    response_model=SubscriptionResponse,
)
def get_subscription(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Current organization's subscription; auto-provisions the free tier."""
    subscription = SubscriptionService().get_or_create_subscription(
        db, organization_id=ctx.organization_id
    )
    db.commit()
    return _subscription_response(subscription)


@router.post(
    "/billing/subscription/plan",
    response_model=ChangePlanResponse,
)
def change_plan(
    body: ChangePlanRequest,
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Switch plan (admin only). Manual billing mode until a payment provider
    is integrated; see docs/MONETIZATION.md for the checkout integration point."""
    subscription = SubscriptionService().change_plan(
        db,
        organization_id=ctx.organization_id,
        plan_code=body.plan_code,
        actor_user_id=ctx.user_id,
    )
    db.commit()
    return ChangePlanResponse(
        subscription=_subscription_response(subscription),
        checkout="manual",
    )


@router.get(
    "/billing/usage",
    response_model=UsageResponse,
)
def get_usage(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Current usage metered against the organization's plan limits."""
    service = SubscriptionService()
    subscription = service.get_or_create_subscription(db, organization_id=ctx.organization_id)
    usage = service.get_usage(db, organization_id=ctx.organization_id)
    db.commit()

    meter_map = {
        "active_jobs": "active_jobs",
        "screenings_per_month": "screenings_this_month",
        "seats": "seats",
    }
    meters: list[UsageMeterResponse] = []
    for limit_key, usage_key in meter_map.items():
        limit = int(subscription.plan.limits.get(limit_key, -1))
        used = int(usage.get(usage_key, 0))
        unlimited = limit < 0
        meters.append(
            UsageMeterResponse(
                meter=limit_key,
                used=used,
                limit=limit,
                unlimited=unlimited,
                percent_used=None if unlimited or limit == 0 else round(used / limit * 100, 1),
            )
        )
    return UsageResponse(plan_code=subscription.plan.code, meters=meters)

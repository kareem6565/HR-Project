from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CandidateEvaluation,
    Job,
    JobApplication,
    Organization,
    OrganizationSubscription,
    Plan,
    User,
)
from app.services.audit_service import AuditService
from app.services.errors import NotFoundError, ValidationError

FREE_PLAN_CODE = "free"

# Monetization v1 catalog. ``-1`` means unlimited. Seeded idempotently by plan
# code so the catalog can evolve in code while existing rows stay stable.
DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "code": "free",
        "name": "Starter",
        "description": "Try HERA with a real screening pipeline for your first roles.",
        "price_monthly_cents": 0,
        "currency": "USD",
        "limits": {"active_jobs": 3, "screenings_per_month": 50, "seats": 2},
        "features": {
            "talent_pool": True,
            "interview_scheduling": True,
            "ocr_cv_intake": False,
            "priority_support": False,
        },
        "sort_order": 0,
    },
    {
        "code": "pro",
        "name": "Pro",
        "description": "For growing teams screening at volume every week.",
        "price_monthly_cents": 4900,
        "currency": "USD",
        "limits": {"active_jobs": 25, "screenings_per_month": 1000, "seats": 10},
        "features": {
            "talent_pool": True,
            "interview_scheduling": True,
            "ocr_cv_intake": True,
            "priority_support": True,
        },
        "sort_order": 1,
    },
    {
        "code": "business",
        "name": "Business",
        "description": "High-volume hiring with uncapped roles and dedicated support.",
        "price_monthly_cents": 19900,
        "currency": "USD",
        "limits": {"active_jobs": -1, "screenings_per_month": 10000, "seats": -1},
        "features": {
            "talent_pool": True,
            "interview_scheduling": True,
            "ocr_cv_intake": True,
            "priority_support": True,
            "audit_exports": True,
        },
        "sort_order": 2,
    },
]


class SubscriptionService:
    """Plans, organization subscriptions, and usage metering (monetization v1).

    Enforcement of plan limits on existing product flows is intentionally out
    of scope for v1: this service exposes limits and usage so the UI can show
    them, and a later change can enforce at the edges without touching scoring
    or decision logic.
    """

    def ensure_default_plans(self, db: Session) -> None:
        existing = set(db.scalars(select(Plan.code)).all())
        for spec in DEFAULT_PLANS:
            if spec["code"] not in existing:
                db.add(Plan(**spec))
        db.flush()

    def list_plans(self, db: Session) -> list[Plan]:
        self.ensure_default_plans(db)
        return list(
            db.scalars(select(Plan).where(Plan.status == "active").order_by(Plan.sort_order)).all()
        )

    def get_or_create_subscription(
        self, db: Session, *, organization_id: uuid.UUID
    ) -> OrganizationSubscription:
        subscription = db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == organization_id
            )
        )
        if subscription is not None:
            return subscription

        self.ensure_default_plans(db)
        free_plan = db.scalar(select(Plan).where(Plan.code == FREE_PLAN_CODE))
        if free_plan is None:  # pragma: no cover - ensure_default_plans guarantees it
            raise NotFoundError("Default plan catalog is unavailable.")
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organization was not found.")
        subscription = OrganizationSubscription(
            organization_id=organization_id,
            plan_id=free_plan.id,
            status="active",
            provider="none",
        )
        db.add(subscription)
        db.flush()
        return subscription

    def change_plan(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        plan_code: str,
        actor_user_id: uuid.UUID,
    ) -> OrganizationSubscription:
        """Switch the organization's plan (manual billing mode).

        Payment collection is the documented integration point: until a payment
        provider is configured, paid tiers are activated with provider="manual"
        (invoiced outside the product). When a provider is integrated this is
        where checkout-session creation and webhook-driven activation attach.
        """
        self.ensure_default_plans(db)
        plan = db.scalar(select(Plan).where(Plan.code == plan_code, Plan.status == "active"))
        if plan is None:
            raise ValidationError("Unknown or unavailable plan.")

        subscription = self.get_or_create_subscription(db, organization_id=organization_id)
        previous_code = subscription.plan.code if subscription.plan else None
        if previous_code == plan.code:
            return subscription

        now = datetime.now(UTC)
        subscription.plan_id = plan.id
        subscription.plan = plan
        subscription.status = "active"
        subscription.provider = "none" if plan.price_monthly_cents == 0 else "manual"
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=30)
        subscription.cancel_at_period_end = False
        db.flush()

        AuditService().log_event(
            db,
            action="billing.plan_changed",
            entity_type="organization_subscription",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            entity_id=subscription.id,
            metadata={
                "from_plan": previous_code,
                "to_plan": plan.code,
                "provider": subscription.provider,
            },
        )
        return subscription

    def get_usage(self, db: Session, *, organization_id: uuid.UUID) -> dict[str, int | None]:
        """Current usage against metered limits for this organization."""
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        active_jobs = db.scalar(
            select(func.count(Job.id)).where(
                Job.organization_id == organization_id, Job.status == "active"
            )
        )
        screenings_this_month = db.scalar(
            select(func.count(CandidateEvaluation.id))
            .join(
                JobApplication,
                JobApplication.id == CandidateEvaluation.job_application_id,
            )
            .where(
                JobApplication.organization_id == organization_id,
                CandidateEvaluation.created_at >= month_start,
            )
        )
        seats = db.scalar(
            select(func.count(User.id)).where(
                User.organization_id == organization_id, User.status == "active"
            )
        )
        return {
            "active_jobs": int(active_jobs or 0),
            "screenings_this_month": int(screenings_this_month or 0),
            "seats": int(seats or 0),
        }

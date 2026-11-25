from __future__ import annotations

import uuid
from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models import Job, Organization, User
from app.services.subscription_service import SubscriptionService


@pytest.fixture()
def client(db_session: Session) -> Generator[httpx.Client, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _org_user(db: Session, suffix: str, role: str = "admin") -> tuple[Organization, User]:
    organization = Organization(name=f"Billing Org {suffix}")
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email=f"billing-{suffix}@example.com",
        full_name="Billing HR",
        role=role,
    )
    db.add(user)
    db.flush()
    return organization, user


def _headers(org: Organization, user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id), "X-Organization-Id": str(org.id)}


def test_plans_catalog_seeded_and_ordered(client: httpx.Client, db_session: Session) -> None:
    org, user = _org_user(db_session, "plans")
    resp = client.get("/api/v1/billing/plans", headers=_headers(org, user))
    assert resp.status_code == 200
    plans = resp.json()
    codes = [p["code"] for p in plans]
    assert codes == ["free", "pro", "business"]
    assert plans[0]["price_monthly_cents"] == 0
    assert plans[1]["limits"]["screenings_per_month"] == 1000
    assert plans[2]["limits"]["active_jobs"] == -1
    assert plans[1]["features"]["ocr_cv_intake"] is True
    assert plans[0]["features"]["ocr_cv_intake"] is False


def test_subscription_auto_provisions_free_tier(client: httpx.Client, db_session: Session) -> None:
    org, user = _org_user(db_session, "auto")
    resp = client.get("/api/v1/billing/subscription", headers=_headers(org, user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["code"] == "free"
    assert body["status"] == "active"
    assert body["provider"] == "none"
    # Idempotent: second read returns the same subscription row
    resp2 = client.get("/api/v1/billing/subscription", headers=_headers(org, user))
    assert resp2.json()["id"] == body["id"]


def test_change_plan_admin_only_and_manual_provider(
    client: httpx.Client, db_session: Session
) -> None:
    org, admin = _org_user(db_session, "admin")
    recruiter = User(
        organization_id=org.id,
        email="billing-recruiter@example.com",
        full_name="Recruiter",
        role="recruiter",
    )
    db_session.add(recruiter)
    db_session.flush()

    denied = client.post(
        "/api/v1/billing/subscription/plan",
        json={"plan_code": "pro"},
        headers=_headers(org, recruiter),
    )
    assert denied.status_code == 403

    resp = client.post(
        "/api/v1/billing/subscription/plan",
        json={"plan_code": "pro"},
        headers=_headers(org, admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription"]["plan"]["code"] == "pro"
    assert body["subscription"]["provider"] == "manual"
    assert body["subscription"]["current_period_end"] is not None
    assert body["checkout"] == "manual"

    # Downgrade back to free clears billing provider
    back = client.post(
        "/api/v1/billing/subscription/plan",
        json={"plan_code": "free"},
        headers=_headers(org, admin),
    )
    assert back.status_code == 200
    assert back.json()["subscription"]["provider"] == "none"


def test_change_plan_rejects_unknown_code(client: httpx.Client, db_session: Session) -> None:
    org, admin = _org_user(db_session, "unknown")
    resp = client.post(
        "/api/v1/billing/subscription/plan",
        json={"plan_code": "enterprise-plus-ultra"},
        headers=_headers(org, admin),
    )
    assert resp.status_code in (400, 422)


def test_usage_meters_reflect_org_data(client: httpx.Client, db_session: Session) -> None:
    org, admin = _org_user(db_session, "usage")
    for i in range(2):
        db_session.add(
            Job(
                organization_id=org.id,
                title=f"Role {i}",
                status="active",
                created_by_user_id=admin.id,
            )
        )
    db_session.flush()

    resp = client.get("/api/v1/billing/usage", headers=_headers(org, admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_code"] == "free"
    meters = {m["meter"]: m for m in body["meters"]}
    assert meters["active_jobs"]["used"] == 2
    assert meters["active_jobs"]["limit"] == 3
    assert meters["active_jobs"]["percent_used"] == pytest.approx(66.7, abs=0.1)
    assert meters["seats"]["used"] == 1
    assert meters["screenings_per_month"]["used"] == 0

    # Unlimited meters render as unlimited on business
    client.post(
        "/api/v1/billing/subscription/plan",
        json={"plan_code": "business"},
        headers=_headers(org, admin),
    )
    resp2 = client.get("/api/v1/billing/usage", headers=_headers(org, admin))
    meters2 = {m["meter"]: m for m in resp2.json()["meters"]}
    assert meters2["active_jobs"]["unlimited"] is True
    assert meters2["active_jobs"]["percent_used"] is None


def test_usage_is_org_scoped(client: httpx.Client, db_session: Session) -> None:
    org_a, admin_a = _org_user(db_session, "iso-a")
    org_b, admin_b = _org_user(db_session, "iso-b")
    db_session.add(
        Job(
            organization_id=org_b.id,
            title="Other org role",
            status="active",
            created_by_user_id=admin_b.id,
        )
    )
    db_session.flush()
    resp = client.get("/api/v1/billing/usage", headers=_headers(org_a, admin_a))
    meters = {m["meter"]: m for m in resp.json()["meters"]}
    assert meters["active_jobs"]["used"] == 0


def test_change_plan_writes_audit_event(client: httpx.Client, db_session: Session) -> None:
    from app.models import AuditLog

    org, admin = _org_user(db_session, "audit")
    client.post(
        "/api/v1/billing/subscription/plan",
        json={"plan_code": "pro"},
        headers=_headers(org, admin),
    )
    events = [
        row
        for row in db_session.query(AuditLog).all()
        if row.action == "billing.plan_changed" and row.organization_id == org.id
    ]
    assert len(events) == 1
    assert events[0].actor_user_id == admin.id


def test_service_change_plan_idempotent_same_plan(db_session: Session) -> None:
    org, admin = _org_user(db_session, "idem")
    service = SubscriptionService()
    sub1 = service.change_plan(
        db_session,
        organization_id=org.id,
        plan_code="pro",
        actor_user_id=admin.id,
    )
    sub2 = service.change_plan(
        db_session,
        organization_id=org.id,
        plan_code="pro",
        actor_user_id=admin.id,
    )
    assert sub1.id == sub2.id
    assert sub2.plan.code == "pro"


def test_non_member_org_cannot_read_billing(client: httpx.Client, db_session: Session) -> None:
    org, admin = _org_user(db_session, "member")
    rogue_headers = {"X-User-Id": str(uuid.uuid4()), "X-Organization-Id": str(uuid.uuid4())}
    resp = client.get("/api/v1/billing/subscription", headers=rogue_headers)
    assert resp.status_code in (401, 403, 404)

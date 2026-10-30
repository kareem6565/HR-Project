"""Comprehensive test suite for Authentication, Roles, Authorization, and Bootstrap (Prompt 2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from starlette.testclient import TestClient

from app.cli.bootstrap import bootstrap_admin
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import create_app
from app.models.organization import Organization
from app.models.user import User
from app.services.user_service import UserService


@pytest.fixture()
def client(db_session):
    """Provide a test client wired to the active database session."""
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def seeded_org(db_session) -> Organization:
    org = Organization(name="Hera Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def seeded_admin(db_session, seeded_org) -> User:
    admin = UserService().create(
        db_session,
        organization_id=seeded_org.id,
        email="admin@heratest.com",
        full_name="Admin User",
        password="ValidAdminPassword123!",
        role="admin",
    )
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture()
def seeded_recruiter(db_session, seeded_org) -> User:
    recruiter = UserService().create(
        db_session,
        organization_id=seeded_org.id,
        email="recruiter@heratest.com",
        full_name="Recruiter User",
        password="ValidRecruiterPassword123!",
        role="recruiter",
    )
    db_session.commit()
    db_session.refresh(recruiter)
    return recruiter


# ==============================================================================
# 1. Password Hashing & Verification Tests
# ==============================================================================


def test_password_hash_and_verification() -> None:
    raw_password = "SuperSecretPassword123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$argon2id$")
    assert raw_password not in hashed

    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(raw_password, "") is False
    assert verify_password(raw_password, None) is False


def test_empty_password_hashing_raises() -> None:
    with pytest.raises(ValueError, match="Password cannot be empty"):
        hash_password("")


# ==============================================================================
# 2. JWT Access Token Generation and Decoding
# ==============================================================================


def test_create_and_decode_valid_access_token() -> None:
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        organization_id=org_id,
        role="admin",
        token_version=2,
    )

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["org_id"] == str(org_id)
    assert payload["role"] == "admin"
    assert payload["token_version"] == 2
    assert payload["iss"] == settings.jwt_issuer
    assert payload["aud"] == settings.jwt_audience


def test_decode_expired_token_raises() -> None:
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    expired_token = create_access_token(
        user_id=user_id,
        organization_id=org_id,
        role="recruiter",
        token_version=1,
        expires_delta=timedelta(seconds=-10),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_decode_invalid_signature_raises() -> None:
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    valid_token = create_access_token(
        user_id=user_id,
        organization_id=org_id,
        role="recruiter",
        token_version=1,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            valid_token,
            "completely-wrong-secret-key-32chars-minimum-length",
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )


def test_decode_malformed_token_raises() -> None:
    with pytest.raises(jwt.DecodeError):
        decode_access_token("this-is-not-a-valid-jwt-token")


# ==============================================================================
# 3. Authentication Endpoints: POST /auth/login
# ==============================================================================


def test_login_success(client, seeded_recruiter) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "recruiter@heratest.com", "password": "ValidRecruiterPassword123!"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.jwt_expire_minutes * 60
    assert data["user"]["email"] == "recruiter@heratest.com"
    assert data["user"]["role"] == "recruiter"
    assert "password_hash" not in str(data)
    assert "jwt_secret_key" not in str(data)


def test_login_case_insensitive_email(client, seeded_recruiter) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "RECRUITER@HERATEST.COM", "password": "ValidRecruiterPassword123!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_incorrect_password(client, seeded_recruiter) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "recruiter@heratest.com", "password": "WrongPassword!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_login_unknown_account(client) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@unknown.com", "password": "AnyPassword123!"},
    )
    assert resp.status_code == 401
    # Generic message prevents user enumeration
    assert resp.json()["detail"] == "Invalid email or password."


def test_login_inactive_account(client, db_session, seeded_recruiter) -> None:
    seeded_recruiter.is_active = False
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_recruiter.email, "password": "ValidRecruiterPassword123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_login_legacy_user_without_password_hash(client, db_session, seeded_org) -> None:
    legacy_user = User(
        organization_id=seeded_org.id,
        email="legacy@heratest.com",
        full_name="Legacy User",
        password_hash=None,
        role="recruiter",
        is_active=True,
        status="active",
    )
    db_session.add(legacy_user)
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy@heratest.com", "password": "AnyPassword!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def _hr_manager_assertion(
    employee_code: str = "HR001", role: str = "hr", secret: str | None = None
) -> str:
    now = int(datetime.now(UTC).timestamp())
    return jwt.encode(
        {
            "iss": settings.hr_sso_issuer,
            "aud": "hera-recruitment",
            "sub": employee_code,
            "name": "Hera HR User",
            "role": role,
            "iat": now,
            "exp": now + 45,
        },
        secret or settings.hr_sso_shared_secret,
        algorithm="HS256",
    )


def test_hr_sso_exchange_provisions_recruiter(client, seeded_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "hr_sso_shared_secret", "test-shared-hr-secret-key-with-32chars")
    monkeypatch.setattr(settings, "hr_sso_organization_id", str(seeded_org.id))

    response = client.post(
        "/api/v1/auth/sso/exchange",
        json={"assertion": _hr_manager_assertion()},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "hrm.hr001@sso.hera.local"
    assert data["user"]["role"] == "recruiter"
    assert data["user"]["roles"] == ["recruiter", "hr_operations"]
    profile = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert profile.status_code == 200
    assert profile.json()["id"] == data["user"]["id"]
    assert set(profile.json()["roles"]) == {"recruiter", "hr_operations"}
    recruitment = client.get(
        "/api/v1/jobs", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert recruitment.status_code == 200

    second_response = client.post(
        "/api/v1/auth/sso/exchange",
        json={"assertion": _hr_manager_assertion()},
    )
    assert second_response.status_code == 200
    assert second_response.json()["user"]["id"] == data["user"]["id"]


def test_hr_sso_exchange_rejects_invalid_assertion(client, seeded_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "hr_sso_shared_secret", "test-shared-hr-secret-key-with-32chars")
    monkeypatch.setattr(settings, "hr_sso_organization_id", str(seeded_org.id))

    response = client.post(
        "/api/v1/auth/sso/exchange",
        json={"assertion": _hr_manager_assertion(secret="wrong-shared-secret-key-32-characters")},
    )

    assert response.status_code == 401


def test_hr_sso_exchange_rejects_non_hr_role(client, seeded_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "hr_sso_shared_secret", "test-shared-hr-secret-key-with-32chars")
    monkeypatch.setattr(settings, "hr_sso_organization_id", str(seeded_org.id))

    response = client.post(
        "/api/v1/auth/sso/exchange",
        json={"assertion": _hr_manager_assertion(role="employee")},
    )

    assert response.status_code == 403


def test_hr_sso_exchange_reports_missing_organization_setup(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "hr_sso_shared_secret", "test-shared-hr-secret-key-with-32chars")
    monkeypatch.setattr(settings, "hr_sso_organization_id", str(uuid.uuid4()))

    response = client.post(
        "/api/v1/auth/sso/exchange",
        json={"assertion": _hr_manager_assertion()},
    )

    assert response.status_code == 503
    assert "organization" in response.json()["detail"].lower()


def test_hr_sso_exchange_reports_invalid_organization_configuration(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "hr_sso_shared_secret", "test-shared-hr-secret-key-with-32chars")
    monkeypatch.setattr(settings, "hr_sso_organization_id", "not-a-uuid")

    response = client.post(
        "/api/v1/auth/sso/exchange",
        json={"assertion": _hr_manager_assertion()},
    )

    assert response.status_code == 503
    assert "organization id is invalid" in response.json()["detail"].lower()


# ==============================================================================
# 4. Identity Endpoint: GET /auth/me
# ==============================================================================


def test_auth_me_with_valid_bearer_token(client, seeded_recruiter) -> None:
    token = create_access_token(
        user_id=seeded_recruiter.id,
        organization_id=seeded_recruiter.organization_id,
        role=seeded_recruiter.role,
        token_version=seeded_recruiter.token_version,
    )
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(seeded_recruiter.id)
    assert data["email"] == seeded_recruiter.email
    assert data["role"] == "recruiter"
    assert data["roles"] == ["recruiter"]
    assert data["organization_id"] == str(seeded_recruiter.organization_id)
    assert "password_hash" not in data


def test_auth_me_rejects_missing_token(client) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_auth_me_rejects_legacy_headers_without_bearer_token(client, seeded_recruiter) -> None:
    resp = client.get(
        "/api/v1/auth/me",
        headers={
            "X-User-Id": str(seeded_recruiter.id),
            "X-Organization-Id": str(seeded_recruiter.organization_id),
        },
    )
    assert resp.status_code == 401


def test_auth_me_rejects_legacy_identity_headers_in_production(
    client, seeded_recruiter, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "X-User-Id": str(seeded_recruiter.id),
            "X-Organization-Id": str(seeded_recruiter.organization_id),
        },
    )

    assert response.status_code == 401


def test_auth_me_rejects_expired_token(client, seeded_recruiter) -> None:
    token = create_access_token(
        user_id=seeded_recruiter.id,
        organization_id=seeded_recruiter.organization_id,
        role=seeded_recruiter.role,
        token_version=seeded_recruiter.token_version,
        expires_delta=timedelta(seconds=-1),
    )
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_auth_me_rejects_tampered_token(client, seeded_recruiter) -> None:
    token = create_access_token(
        user_id=seeded_recruiter.id,
        organization_id=seeded_recruiter.organization_id,
        role=seeded_recruiter.role,
        token_version=seeded_recruiter.token_version,
    )
    tampered_token = token[:-5] + "aaaaa"
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert resp.status_code == 401


# ==============================================================================
# 5. Logout & Revocation: POST /auth/logout
# ==============================================================================


def test_logout_invalidates_active_token(client, seeded_recruiter) -> None:
    token = create_access_token(
        user_id=seeded_recruiter.id,
        organization_id=seeded_recruiter.organization_id,
        role=seeded_recruiter.role,
        token_version=seeded_recruiter.token_version,
    )

    # Token works initially
    me_resp1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp1.status_code == 200

    # Perform logout
    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200
    assert logout_resp.json()["detail"] == "Logged out successfully."

    # Using the same token now fails because token_version was incremented
    me_resp2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp2.status_code == 401
    assert "revoked" in me_resp2.json()["detail"].lower()


# ==============================================================================
# 6. Role-Based Access Control: 401 vs 403 & Admin-Only Operations
# ==============================================================================


def test_unauthenticated_request_to_business_endpoint_returns_401(client) -> None:
    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 401


def test_recruiter_forbidden_from_admin_ai_settings(client, seeded_recruiter) -> None:
    recruiter_token = create_access_token(
        user_id=seeded_recruiter.id,
        organization_id=seeded_recruiter.organization_id,
        role=seeded_recruiter.role,
        token_version=seeded_recruiter.token_version,
    )
    h = {"Authorization": f"Bearer {recruiter_token}"}

    # Recruiter attempting to modify AI settings receives 403 Forbidden
    resp = client.post("/api/v1/settings/ai/api-key", json={"api_key": "some-key"}, headers=h)
    assert resp.status_code == 403

    resp_del = client.delete("/api/v1/settings/ai/api-key", headers=h)
    assert resp_del.status_code == 403


def test_recruiter_forbidden_from_user_provisioning(client, seeded_recruiter) -> None:
    recruiter_token = create_access_token(
        user_id=seeded_recruiter.id,
        organization_id=seeded_recruiter.organization_id,
        role=seeded_recruiter.role,
        token_version=seeded_recruiter.token_version,
    )
    h = {"Authorization": f"Bearer {recruiter_token}"}

    resp = client.post(
        "/api/v1/users",
        json={"email": "newrecruiter@test.com", "full_name": "New Recruiter"},
        headers=h,
    )
    assert resp.status_code == 403


def test_hr_operations_only_user_cannot_access_recruitment_api(
    client, db_session, seeded_org
) -> None:
    hr_only = User(
        organization_id=seeded_org.id,
        email="hr-only@heratest.com",
        full_name="HR Operations Only",
        role="recruiter",
        roles=["hr_operations"],
        password_hash=None,
    )
    db_session.add(hr_only)
    db_session.commit()

    token = create_access_token(
        user_id=hr_only.id,
        organization_id=hr_only.organization_id,
        role=hr_only.role,
        roles=hr_only.effective_roles,
        token_version=hr_only.token_version,
    )
    response = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert "admin, recruiter" in response.json()["detail"]


def test_admin_can_access_ai_settings_and_provision_users(client, seeded_admin) -> None:
    admin_token = create_access_token(
        user_id=seeded_admin.id,
        organization_id=seeded_admin.organization_id,
        role=seeded_admin.role,
        token_version=seeded_admin.token_version,
    )
    h = {"Authorization": f"Bearer {admin_token}"}

    # Admin can view AI settings, but runtime mutation is disabled to prevent cross-tenant changes
    resp_get = client.get("/api/v1/settings/ai", headers=h)
    assert resp_get.status_code == 200

    resp_set = client.post(
        "/api/v1/settings/ai/api-key", json={"api_key": "sk-admin-test-key"}, headers=h
    )
    assert resp_set.status_code == 405

    resp_del = client.delete("/api/v1/settings/ai/api-key", headers=h)
    assert resp_del.status_code == 405

    # Admin can provision new user for their organization
    resp_user = client.post(
        "/api/v1/users",
        json={
            "email": "provisioned@test.com",
            "full_name": "Provisioned User",
            "password": "Password123!",
            "role": "recruiter",
        },
        headers=h,
    )
    assert resp_user.status_code == 201
    user_data = resp_user.json()
    assert user_data["email"] == "provisioned@test.com"
    assert user_data["role"] == "recruiter"
    assert user_data["organization_id"] == str(seeded_admin.organization_id)
    assert "password_hash" not in user_data


def test_admin_cannot_provision_for_other_organization(client, db_session, seeded_admin) -> None:
    other_org = Organization(name="Other Company")
    db_session.add(other_org)
    db_session.commit()

    admin_token = create_access_token(
        user_id=seeded_admin.id,
        organization_id=seeded_admin.organization_id,
        role=seeded_admin.role,
        token_version=seeded_admin.token_version,
    )
    h = {"Authorization": f"Bearer {admin_token}"}

    # Calling with route param for another organization -> 403 Forbidden
    resp = client.post(
        f"/api/v1/organizations/{other_org.id}/users",
        json={"email": "attacker@other.com", "full_name": "Attacker"},
        headers=h,
    )
    assert resp.status_code == 403
    assert "Cannot provision users for another organization" in resp.json()["detail"]


def test_legacy_default_user_is_not_admin(db_session, seeded_org) -> None:
    # A newly created user defaults to role='recruiter'
    user = User(
        organization_id=seeded_org.id,
        email="plain@test.com",
        full_name="Plain User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.role == "recruiter"
    assert user.role != "admin"


# ==============================================================================
# 7. CLI Administrator Bootstrap Tests
# ==============================================================================


def test_bootstrap_admin_creates_new_organization_and_admin(db_session) -> None:
    user = bootstrap_admin(
        db_session,
        org_name="Fresh Startup",
        email="founder@startup.com",
        full_name="Founder Person",
        password="ValidPassword123!",
    )
    assert user.role == "admin"
    assert user.email == "founder@startup.com"
    assert user.is_active is True
    assert verify_password("ValidPassword123!", user.password_hash) is True


def test_bootstrap_admin_refuses_duplicate_admin_for_same_org(db_session, seeded_admin) -> None:
    with pytest.raises(ValueError, match="already has active administrator"):
        bootstrap_admin(
            db_session,
            org_id=str(seeded_admin.organization_id),
            email="secondadmin@heratest.com",
            full_name="Second Admin",
            password="ValidPassword123!",
        )


def test_bootstrap_admin_refuses_existing_user_without_reset_flag(
    db_session, seeded_recruiter
) -> None:
    with pytest.raises(ValueError, match="already exists in organization"):
        bootstrap_admin(
            db_session,
            org_id=str(seeded_recruiter.organization_id),
            email=seeded_recruiter.email,
            full_name="Recruiter",
            password="NewPassword123!",
            reset_existing=False,
        )


def test_bootstrap_admin_promotes_existing_user_with_reset_flag(
    db_session, seeded_recruiter
) -> None:
    promoted = bootstrap_admin(
        db_session,
        org_id=str(seeded_recruiter.organization_id),
        email=seeded_recruiter.email,
        full_name="Promoted Admin",
        password="NewAdminPassword123!",
        reset_existing=True,
    )
    assert promoted.id == seeded_recruiter.id
    assert promoted.role == "admin"
    assert verify_password("NewAdminPassword123!", promoted.password_hash) is True

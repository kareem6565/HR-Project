"""Authentication endpoints for login, session inspection, and logout (Prompt 2)."""

from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.auth import (
    HRSsoExchangeRequest,
    LoginRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.organization import Organization
from app.models.user import User

router = APIRouter()


@router.post("/auth/sso/exchange", response_model=TokenResponse)
def exchange_hr_assertion(
    body: HRSsoExchangeRequest, db: Session = Depends(get_db)
) -> TokenResponse:
    """Exchange a short-lived, PHP-signed HR assertion for a HERA API token."""
    if len(settings.hr_sso_shared_secret) < 32 or not settings.hr_sso_organization_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HR single sign-on is not configured.",
        )

    try:
        organization_id = uuid.UUID(settings.hr_sso_organization_id)
        claims = jwt.decode(
            body.assertion,
            settings.hr_sso_shared_secret,
            algorithms=["HS256"],
            issuer=settings.hr_sso_issuer,
            audience="hera-recruitment",
            options={"require": ["sub", "name", "role", "iat", "exp", "iss", "aud"]},
        )
    except (ValueError, TypeError, jwt.InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired HR sign-in assertion.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    employee_code = claims.get("sub")
    full_name = claims.get("name")
    if (
        claims.get("role") != "hr"
        or not isinstance(employee_code, str)
        or not employee_code.isascii()
        or not employee_code.replace("-", "").replace("_", "").isalnum()
        or not 1 <= len(employee_code) <= 64
        or not isinstance(full_name, str)
        or not full_name.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an authenticated HR account can enter recruitment.",
        )

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The configured HERA organization does not exist.",
        )

    # Stable shadow identity keeps the MySQL account authoritative while HERA
    # retains its own organization-scoped user record in PostgreSQL.
    email = f"hrm.{employee_code.lower()}@sso.hera.local"
    user = db.scalar(
        select(User).where(
            User.organization_id == organization_id,
            func.lower(User.email) == email,
        )
    )
    if user is None:
        user = User(
            organization_id=organization_id,
            email=email,
            full_name=full_name.strip()[:255],
            password_hash=None,
            role="recruiter",
            is_active=True,
            status="active",
            token_version=1,
        )
        db.add(user)
        db.flush()
    elif not user.is_active or user.status != "active" or user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This HR account is not active for recruitment access.",
        )
    else:
        user.full_name = full_name.strip()[:255]

    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        token_version=user.token_version,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserProfileResponse.model_validate(user),
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate with email and password, returning a signed JWT access token.

    Uses a generic authentication failure message that does not disclose whether
    the account exists or its active status.
    """
    email_clean = body.email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == email_clean)
    if body.organization_id is not None:
        stmt = stmt.where(User.organization_id == body.organization_id)

    users = db.scalars(stmt).all()
    if len(users) == 0 or len(users) > 1:
        from app.services.audit_service import AuditService

        AuditService().log_auth_failure(
            db, category="invalid_credentials", organization_id=body.organization_id
        )
        # Generic error message to prevent account enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = users[0]
    if not user.is_active or user.status != "active":
        from app.services.audit_service import AuditService

        AuditService().log_auth_failure(
            db, category="account_inactive", organization_id=user.organization_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.password_hash or not verify_password(body.password, user.password_hash):
        from app.services.audit_service import AuditService

        AuditService().log_auth_failure(
            db, category="invalid_credentials", organization_id=user.organization_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        token_version=user.token_version,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserProfileResponse.model_validate(user),
    )


@router.get("/auth/me", response_model=UserProfileResponse)
def get_current_user_profile(
    ctx: RequestContext = Depends(get_request_context),
) -> UserProfileResponse:
    """Return the authenticated caller's profile and organization context."""
    if ctx.auth_scheme != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserProfileResponse.model_validate(ctx.user)


@router.post("/auth/logout")
def logout(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Revoke all active tokens for the authenticated user by bumping token_version."""
    if ctx.auth_scheme != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    ctx.user.token_version += 1
    db.commit()
    return {"detail": "Logged out successfully."}

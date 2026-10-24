"""API dependency injection for authenticated request context (Prompt 2).

Provides:
- Secure Bearer-token authentication derived from database-backed user records.
- Invalidation via token versioning (logout).
- Role-based authorization via require_roles().
- Legacy X-User-Id / X-Organization-Id headers alone are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from fastapi import Depends, Header, HTTPException, status
import jwt
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User


@dataclass(frozen=True)
class RequestContext:
    """Validated caller identity and role derived from database-backed server session."""

    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    user: User
    auth_scheme: str = "bearer"


async def get_request_context(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_organization_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> RequestContext:
    """Validate Bearer token authentication or local development/test identity headers.

    Derives user, organization, and role from the authoritative database record.
    Rejects missing, expired, revoked, malformed tokens, or inactive accounts.
    """
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization[len("Bearer ") :].strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="The token has expired"'},
            ) from None
        except (jwt.InvalidTokenError, ValueError, KeyError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            ) from None

        try:
            user_uuid = uuid.UUID(payload["sub"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

        user = db.get(User, user_uuid)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active or user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_version = payload.get("token_version")
        if token_version is None or user.token_version != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked.",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token has been revoked"'},
            )

        return RequestContext(
            user_id=user.id,
            organization_id=user.organization_id,
            role=user.role,
            user=user,
            auth_scheme="bearer",
        )

    # Local development / test mode with X-User-Id and X-Organization-Id headers
    if x_user_id is None and x_organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if x_user_id is None or x_organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both X-User-Id and X-Organization-Id headers must be provided.",
        )

    try:
        parsed_user_id = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-User-Id must be a valid UUID.",
        ) from None

    try:
        parsed_org_id = uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Organization-Id must be a valid UUID.",
        ) from None

    from app.models.organization import Organization

    organization = db.get(Organization, parsed_org_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")

    user = db.get(User, parsed_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.organization_id != parsed_org_id:
        raise HTTPException(
            status_code=403,
            detail="User does not belong to the specified organization.",
        )

    if not user.is_active or user.status != "active":
        raise HTTPException(status_code=403, detail="User is not active.")

    return RequestContext(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role or "recruiter",
        user=user,
        auth_scheme="header",
    )


def require_roles(*allowed_roles: str):
    """Dependency factory enforcing role-based access control.

    Returns 401 if unauthenticated; returns 403 if authenticated user lacks required role.
    """

    async def role_checker(
        ctx: RequestContext = Depends(get_request_context),
    ) -> RequestContext:
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles)}.",
            )
        return ctx

    return role_checker

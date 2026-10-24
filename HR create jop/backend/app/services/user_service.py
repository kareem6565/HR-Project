from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, User
from app.services.errors import NotFoundError, ValidationError


class UserService:
    """Minimal user operations for MVP bootstrap."""

    def list_org_users(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
    ) -> list[User]:
        """Return all users in the specified organization, ordered by full name."""
        stmt = (
            select(User)
            .where(User.organization_id == organization_id)
            .order_by(User.full_name.asc())
        )
        return list(db.scalars(stmt).all())

    def create(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        email: str,
        full_name: str,
        password: str | None = None,
        role: str = "recruiter",
    ) -> User:
        """Create a new user in the specified organization."""
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organization was not found.")
        if role not in ("admin", "recruiter"):
            raise ValidationError(f"Invalid role: {role!r}. Allowed roles: 'admin', 'recruiter'.")

        from app.core.security import hash_password

        pwd_hash = hash_password(password) if password else None
        user = User(
            organization_id=organization_id,
            email=email.strip().lower(),
            full_name=full_name.strip(),
            password_hash=pwd_hash,
            role=role,
            is_active=True,
            status="active",
            token_version=1,
        )
        db.add(user)
        db.flush()
        return user


    def get(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> User:
        """Return one user by id, enforcing organization scope."""
        user = db.get(User, user_id)
        if user is None or user.organization_id != organization_id:
            raise NotFoundError("User was not found.")
        return user

    def update_role(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        new_role: str,
        organization_id: uuid.UUID,
    ) -> tuple[User, str, str]:
        """Update role for an organization user and invalidate their existing sessions."""
        user = self.get(db, user_id=user_id, organization_id=organization_id)
        if new_role not in ("admin", "recruiter"):
            raise ValidationError(f"Invalid role: {new_role!r}. Allowed roles: 'admin', 'recruiter'.")
        old_role = user.role
        user.role = new_role
        user.token_version += 1
        db.flush()
        return user, old_role, new_role

    def update_status(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        new_status: str,
        organization_id: uuid.UUID,
    ) -> tuple[User, str, str]:
        """Update user active status (active/inactive) and invalidate tokens on deactivation."""
        user = self.get(db, user_id=user_id, organization_id=organization_id)
        if new_status not in ("active", "inactive", "suspended"):
            raise ValidationError(f"Invalid status: {new_status!r}.")
        old_status = user.status
        user.status = new_status
        user.is_active = (new_status == "active")
        if not user.is_active:
            user.token_version += 1
        db.flush()
        return user, old_status, new_status

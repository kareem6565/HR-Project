"""Operational CLI for secure administrator bootstrap (Prompt 2).

Usage:
    python -m app.cli.bootstrap --org-name "Acme Corp" --email "admin@acme.com" --full-name "Acme Admin"
    python -m app.cli.bootstrap --org-id "<UUID>" --email "admin@acme.com" --full-name "Acme Admin" --reset-existing

Requirements enforced:
- Interactive password input via getpass (or HERA_BOOTSTRAP_PASSWORD for automated setups).
- Rejects default or weak passwords (< 8 characters, common passwords).
- Never prints credentials or tokens to logs/stdout.
- Explicit organization context required.
- Prevents accidental duplicate administrators in the same organization.
- Fails closed when organization or user state is ambiguous.
- Refuses to overwrite existing account without explicit --reset-existing flag.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService

FORBIDDEN_PASSWORDS = {
    "admin",
    "password",
    "12345678",
    "qwerty",
    "admin123",
    "administrator",
    "changeme",
}


def read_and_validate_password() -> str:
    """Read password securely using getpass or environment variable."""
    env_password = os.environ.get("HERA_BOOTSTRAP_PASSWORD")
    if env_password:
        pwd = env_password.strip()
    elif sys.stdin.isatty():
        pwd1 = getpass.getpass("Enter administrator password: ")
        pwd2 = getpass.getpass("Confirm administrator password: ")
        if pwd1 != pwd2:
            raise ValueError("Passwords do not match.")
        pwd = pwd1
    else:
        raise ValueError(
            "Non-interactive terminal detected. Set HERA_BOOTSTRAP_PASSWORD environment variable."
        )

    if len(pwd) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if pwd.lower() in FORBIDDEN_PASSWORDS:
        raise ValueError("Password is too common or weak; default passwords are not permitted.")

    return pwd


def bootstrap_admin(
    db: Session,
    *,
    org_name: str | None = None,
    org_id: str | None = None,
    email: str,
    full_name: str,
    password: str,
    reset_existing: bool = False,
) -> User:
    """Provision an organization administrator account.

    Fails closed on duplicate administrators, ambiguous organizations, or missing context.
    """
    email_clean = email.strip().lower()
    full_name_clean = full_name.strip()

    if not email_clean or "@" not in email_clean:
        raise ValueError("A valid email address is required.")
    if not full_name_clean:
        raise ValueError("Full name cannot be empty.")

    # 1. Resolve Organization Context
    org: Organization | None = None
    if org_id:
        try:
            org_uuid = uuid.UUID(org_id)
        except ValueError:
            raise ValueError(f"Invalid org_id UUID: {org_id!r}") from None
        org = db.get(Organization, org_uuid)
        if org is None:
            raise ValueError(f"Organization with ID {org_id} was not found.")
        if org_name and org.name.lower() != org_name.strip().lower():
            raise ValueError(
                f"Organization name mismatch: specified ID belongs to {org.name!r}, not {org_name!r}."
            )
    elif org_name:
        org_name_clean = org_name.strip()
        matches = db.scalars(
            select(Organization).where(func.lower(Organization.name) == org_name_clean.lower())
        ).all()
        if len(matches) > 1:
            raise ValueError(
                f"Multiple organizations match name {org_name_clean!r}. Specify --org-id explicitly."
            )
        if len(matches) == 1:
            org = matches[0]
        else:
            # Create fresh organization
            org = OrganizationService().create(db, name=org_name_clean)
            db.flush()
    else:
        raise ValueError("Explicit organization context required: specify --org-name or --org-id.")

    # 2. Check Existing Administrator State in this Organization
    active_admins = db.scalars(
        select(User).where(
            User.organization_id == org.id,
            User.role == "admin",
            User.is_active == True,  # noqa: E712
        )
    ).all()

    existing_user = db.scalars(
        select(User).where(
            User.organization_id == org.id,
            func.lower(User.email) == email_clean,
        )
    ).first()

    pwd_hash = hash_password(password)

    if existing_user is not None:
        if not reset_existing:
            raise ValueError(
                f"Account {email_clean!r} already exists in organization {org.name!r}. "
                "Specify --reset-existing to update credentials and promote."
            )
        # Update existing user safely
        existing_user.password_hash = pwd_hash
        existing_user.role = "admin"
        existing_user.is_active = True
        existing_user.status = "active"
        existing_user.full_name = full_name_clean
        existing_user.token_version += 1  # Invalidate any active sessions
        db.commit()
        db.refresh(existing_user)
        return existing_user

    # If creating a brand new user, check whether organization already has an active admin
    if active_admins:
        admin_emails = ", ".join(a.email for a in active_admins)
        raise ValueError(
            f"Organization {org.name!r} already has active administrator(s): {admin_emails}. "
            "To prevent duplicate rogue admins, bootstrap rejected. "
            "Use the existing administrator account or pass --reset-existing with an existing user's email."
        )

    # 3. Create fresh initial administrator
    new_user = UserService().create(
        db,
        organization_id=org.id,
        email=email_clean,
        full_name=full_name_clean,
        password=password,
        role="admin",
    )
    db.commit()
    db.refresh(new_user)
    return new_user


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HERA Administrator Bootstrap: provision the initial organization administrator."
    )
    parser.add_argument(
        "--org-name",
        type=str,
        help="Name of the organization to create or bootstrap.",
    )
    parser.add_argument(
        "--org-id",
        type=str,
        help="UUID of existing organization to bootstrap.",
    )
    parser.add_argument(
        "--email",
        type=str,
        required=True,
        help="Administrator email address.",
    )
    parser.add_argument(
        "--full-name",
        type=str,
        required=True,
        help="Administrator full name.",
    )
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Allow resetting credentials and promoting an existing account to administrator.",
    )

    args = parser.parse_args()

    try:
        password = read_and_validate_password()
    except ValueError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)

    db = SessionLocal()
    try:
        user = bootstrap_admin(
            db,
            org_name=args.org_name,
            org_id=args.org_id,
            email=args.email,
            full_name=args.full_name,
            password=password,
            reset_existing=args.reset_existing,
        )
        sys.stdout.write(
            f"Successfully bootstrapped administrator {user.email!r} for organization {user.organization_id} (role: {user.role}).\n"
        )
    except Exception as exc:
        db.rollback()
        sys.stderr.write(f"Bootstrap failed: {exc}\n")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

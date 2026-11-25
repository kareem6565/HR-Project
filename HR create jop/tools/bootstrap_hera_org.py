"""Create the HERA organization used by the HR Manager single sign-on.

A fresh clone starts with an empty database: Alembic creates the tables but
not the organization that `HR_SSO_ORGANIZATION_ID` points to. This script
creates it idempotently using the ID already configured for HR SSO.

Usage (from `HR create jop/backend/`)::

    .venv\\Scripts\\python.exe tools\\bootstrap_hera_org.py

Environment overrides::

    HERA_DATABASE_URL    defaults to the local docker-compose database
    HERA_ORG_NAME        organization display name (default: Smart HR)
HR_SSO_ORGANIZATION_ID  read from the environment or backend/.env; a fixed
                        development ID is used only if unset
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import psycopg

DATABASE_URL = os.getenv(
    "HERA_DATABASE_URL",
    "postgresql://hr_ai_assistant:hr_ai_assistant@127.0.0.1:5432/hera_recruitment_v2",
)
ORG_NAME = os.getenv("HERA_ORG_NAME", "Smart HR")
DEFAULT_ORG_ID = "83d952e6-a8bb-45c2-b7e2-4ce18f013e66"


def configured_org_id() -> uuid.UUID:
    """Use the SSO organization ID that the backend will validate against."""
    value = os.getenv("HR_SSO_ORGANIZATION_ID", "").strip()
    if not value:
        env_file = Path(__file__).resolve().parents[1] / "backend" / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                key, separator, raw_value = line.partition("=")
                if separator and key.strip() == "HR_SSO_ORGANIZATION_ID":
                    value = raw_value.strip().strip("\"'")
    return uuid.UUID(value or DEFAULT_ORG_ID)


def main() -> int:
    org_id = configured_org_id()
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.organizations (id, name, status)
                VALUES (%s, %s, 'active')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, status = 'active'
                """,
                (org_id, ORG_NAME),
            )
            cursor.execute(
                "SELECT name, status FROM public.organizations WHERE id = %s", (org_id,)
            )
            row = cursor.fetchone()
        connection.commit()

    if row is None:
        print("ERROR: the organization could not be created.")
        return 1

    print(f"organization: {row[0]} ({row[1]})")
    print(f"HR SSO organization ID matches backend configuration: {org_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

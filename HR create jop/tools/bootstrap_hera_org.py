"""Create the HERA organization used by the HR Manager single sign-on.

A fresh clone starts with an empty database: Alembic creates the tables but
not the organization that `HR_SSO_ORGANIZATION_ID` points to. This script
creates it idempotently and prints the UUID to paste into the backend `.env`.

Usage (from `HR create jop/backend/`)::

    .venv\\Scripts\\python.exe tools\\bootstrap_hera_org.py

Environment overrides::

    HERA_DATABASE_URL    defaults to the local docker-compose database
    HERA_ORG_NAME        organization display name (default: Smart HR)
"""

from __future__ import annotations

import os
import sys
import uuid

import psycopg

DATABASE_URL = os.getenv(
    "HERA_DATABASE_URL",
    "postgresql://hr_ai_assistant:hr_ai_assistant@127.0.0.1:5432/hr_ai_assistant",
)
ORG_NAME = os.getenv("HERA_ORG_NAME", "Smart HR")
ORG_ID = uuid.UUID("83d952e6-a8bb-45c2-b7e2-4ce18f013e66")


def main() -> int:
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.organizations (id, name, status)
                VALUES (%s, %s, 'active')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, status = 'active'
                """,
                (ORG_ID, ORG_NAME),
            )
            cursor.execute(
                "SELECT name, status FROM public.organizations WHERE id = %s", (ORG_ID,)
            )
            row = cursor.fetchone()
        connection.commit()

    if row is None:
        print("ERROR: the organization could not be created.")
        return 1

    print(f"organization: {row[0]} ({row[1]})")
    print(f"HR_SSO_ORGANIZATION_ID={ORG_ID}")
    print("add that line to HR create jop/backend/.env")
    return 0


if __name__ == "__main__":
    sys.exit(main())

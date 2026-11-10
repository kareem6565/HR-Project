"""Seed the `hr_ops` schema with the data a fresh install needs to sign in.

The schema itself is created by Alembic (`alembic upgrade head`). This script
only inserts the baseline rows: the default work category, company settings,
leave types, and the accounts used to sign in (system admin, HR, and sample
employees).

It is idempotent: running it again leaves existing rows untouched.

Usage (from `HR create jop/backend/`)::

    .venv\\Scripts\\python.exe tools\\seed_hr_manager.py

Environment overrides::

    HERA_DATABASE_URL   defaults to the local docker-compose database
    HR_SEED_PASSWORD    password for every seeded account (default: hr123)
"""

from __future__ import annotations

import os
import sys

import bcrypt
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "HERA_DATABASE_URL",
    "postgresql://hr_ai_assistant:hr_ai_assistant@127.0.0.1:5432/hr_ai_assistant",
)
SEED_PASSWORD = os.getenv("HR_SEED_PASSWORD", "hr123")

CATEGORY = {
    "name": "الشفت الصباحي (الافتراضي)",
    "shift_type": "day",
    "work_start_time": "09:00:00",
    "work_end_time": "23:00:00",
    "break_start_time": "13:00:00",
    "break_duration_minutes": 60,
    "cutoff_minutes": 60,
    "center_latitude": 29.7770575,
    "center_longitude": 31.2676434,
    "allowed_radius_meters": 5000,
}

COMPANY_SETTINGS = {
    "company_name": "Smart HR",
    "center_latitude": 29.7770575,
    "center_longitude": 31.2676434,
    "allowed_radius_meters": 5000,
}

LEAVE_TYPES = [
    ("annual", "إجازة سنوية", 21.0, 1, 1, 1),
    ("sick", "إجازة مرضية", 14.0, 1, 1, 1),
    ("unpaid", "إجازة بدون راتب", 0.0, 0, 1, 1),
    ("emergency", "إجازة طارئة", 3.0, 1, 1, 1),
]

USERS = [
    ("ADM001", "System Administrator", "admin", 15000.0, 30),
    ("HR001", "مسؤول الموارد البشرية", "hr", 11000.0, 25),
    ("EMP001", "Ahmed Al-Rashidi", "employee", 8500.0, 21),
    ("EMP002", "Fatima Al-Zahraa", "employee", 7200.0, 21),
    ("EMP003", "Omar Khalid", "employee", 9000.0, 25),
    ("EMP004", "Sara Al-Mutairi", "employee", 6800.0, 21),
]


def hash_password(password: str) -> str:
    """Return a bcrypt hash that PHP `password_verify()` accepts."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def main() -> int:
    password_hash = hash_password(SEED_PASSWORD)
    print(f"PostgreSQL: {DATABASE_URL.rsplit('@', 1)[-1]} (schema hr_ops)")

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'hr_ops'"
            )
            if cursor.fetchone() is None:
                print("ERROR: hr_ops schema is missing. Run `alembic upgrade head` first.")
                return 2

            cursor.execute(
                """
                INSERT INTO hr_ops.categories (
                    name, shift_type, work_start_time, work_end_time, break_start_time,
                    break_duration_minutes, cutoff_minutes, center_latitude,
                    center_longitude, allowed_radius_meters
                ) VALUES (
                    %(name)s, %(shift_type)s, %(work_start_time)s, %(work_end_time)s,
                    %(break_start_time)s, %(break_duration_minutes)s, %(cutoff_minutes)s,
                    %(center_latitude)s, %(center_longitude)s, %(allowed_radius_meters)s
                )
                ON CONFLICT DO NOTHING
                """,
                CATEGORY,
            )

            cursor.execute(
                """
                INSERT INTO hr_ops.company_settings (
                    company_name, center_latitude, center_longitude, allowed_radius_meters
                ) VALUES (
                    %(company_name)s, %(center_latitude)s, %(center_longitude)s,
                    %(allowed_radius_meters)s
                )
                ON CONFLICT DO NOTHING
                """,
                COMPANY_SETTINGS,
            )

            for code, name, default_days, is_paid, requires_manager, is_active in LEAVE_TYPES:
                cursor.execute(
                    """
                    INSERT INTO hr_ops.leave_types (
                        code, name, default_days, is_paid, requires_manager_approval, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (code) DO NOTHING
                    """,
                    (code, name, default_days, is_paid, requires_manager, is_active),
                )

            cursor.execute("SELECT id FROM hr_ops.categories ORDER BY id LIMIT 1")
            category_row = cursor.fetchone()
            category_id = category_row["id"] if category_row else None

            for emp_code, name, role, salary, vacation_days in USERS:
                cursor.execute(
                    """
                    INSERT INTO hr_ops.users (
                        emp_code, name, password_hash, role, category_id,
                        basic_salary, yearly_vacation_days
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (emp_code) DO NOTHING
                    """,
                    (emp_code, name, password_hash, role, category_id, salary, vacation_days),
                )

            cursor.execute("SELECT COUNT(*) AS total FROM hr_ops.users")
            user_count = cursor.fetchone()["total"]

        connection.commit()

    print(f"seeded hr_ops: users={user_count}, leave_types={len(LEAVE_TYPES)}")
    print(f"sign in with employee code HR001 and password {SEED_PASSWORD}")
    print("change the password from the employee management screen before real use")
    return 0


if __name__ == "__main__":
    sys.exit(main())

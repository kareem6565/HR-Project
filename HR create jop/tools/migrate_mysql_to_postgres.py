"""One-off migration of the legacy MySQL `attendance_db` into PostgreSQL.

The PHP HR Manager application used to own a separate MySQL database. The
single HERA database now hosts those tables in the `hr_ops` schema (created by
Alembic revision ``020_hr_ops_schema``). This tool copies every legacy table,
preserves primary keys, resets identity sequences, and verifies the result.

Usage (from ``backend/`` so the project venv is used)::

    backend\\.venv\\Scripts\\python.exe tools\\migrate_mysql_to_postgres.py

Environment overrides::

    LEGACY_MYSQL_HOST / PORT / USER / PASSWORD / DATABASE
    HERA_DATABASE_URL (defaults to the local docker-compose database)

The script is idempotent: it truncates ``hr_ops`` before copying.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pymysql
from psycopg import sql
from psycopg.rows import dict_row

MYSQL_CONFIG = {
    "host": os.getenv("LEGACY_MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("LEGACY_MYSQL_PORT", "3306")),
    "user": os.getenv("LEGACY_MYSQL_USER", "root"),
    "password": os.getenv("LEGACY_MYSQL_PASSWORD", ""),
    "database": os.getenv("LEGACY_MYSQL_DATABASE", "attendance_db"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

PG_DSN = os.getenv(
    "HERA_DATABASE_URL",
    "postgresql://hr_ai_assistant:hr_ai_assistant@127.0.0.1:5432/hr_ai_assistant",
)

# Foreign-key safe insert order. `audit_logs` only references users.
TABLES = [
    "categories",
    "users",
    "company_settings",
    "attendance",
    "geofence_events",
    "work_submissions",
    "leave_types",
    "leave_balances",
    "leave_requests",
    "payroll_runs",
    "payroll_adjustments",
    "payroll_items",
    "employee_documents",
    "hr_letters",
    "notifications",
    "audit_logs",
]


def normalize(value: Any, column: str) -> Any:
    """Convert driver-specific values into a stable, comparable form."""
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return time(total // 3600, (total % 3600) // 60, total % 60).isoformat()
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if column == "details" and isinstance(value, str):
        try:
            return json.dumps(json.loads(value), sort_keys=True, ensure_ascii=False)
        except ValueError:
            return value
    return value


def signature(rows: list[dict[str, Any]], columns: list[str]) -> str:
    payload = [[normalize(row.get(column), column) for column in columns] for row in rows]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def fetch_mysql(connection: pymysql.connections.Connection, table: str):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM `{table}`")
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
    return rows, columns


def fetch_postgres(cursor, table: str):
    cursor.execute(sql.SQL("SELECT * FROM hr_ops.{} ORDER BY 1").format(sql.Identifier(table)))
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    return rows, columns


def main() -> int:
    target = PG_DSN.rsplit("@", 1)[-1]
    print(
        f"MySQL : {MYSQL_CONFIG['user']}@{MYSQL_CONFIG['host']}:"
        f"{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}"
    )
    print(f"PostgreSQL: {target} (schema hr_ops)")

    mysql_connection = pymysql.connect(**MYSQL_CONFIG)
    pg_connection = psycopg.connect(PG_DSN, row_factory=dict_row)
    failures: list[str] = []

    try:
        with pg_connection.cursor() as pg_cursor:
            pg_cursor.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'hr_ops'"
            )
            if pg_cursor.fetchone() is None:
                print("ERROR: hr_ops schema is missing. Run `alembic upgrade head` first.")
                return 2

            truncate = sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                sql.SQL(", ").join(
                    sql.SQL("hr_ops.{}").format(sql.Identifier(table)) for table in reversed(TABLES)
                )
            )
            pg_cursor.execute(truncate)

            for table in TABLES:
                mysql_rows, mysql_columns = fetch_mysql(mysql_connection, table)
                if not mysql_rows:
                    print(f"{table:<24} 0 rows (skipped)")
                    continue

                insert = sql.SQL("INSERT INTO hr_ops.{table} ({columns}) VALUES ({values})").format(
                    table=sql.Identifier(table),
                    columns=sql.SQL(", ").join(sql.Identifier(column) for column in mysql_columns),
                    values=sql.SQL(", ").join(sql.Placeholder() for _ in mysql_columns),
                )
                pg_cursor.executemany(
                    insert,
                    [
                        tuple(normalize(row[column], column) for column in mysql_columns)
                        for row in mysql_rows
                    ],
                )
                print(f"{table:<24} {len(mysql_rows)} rows copied")

            for table in TABLES:
                pg_cursor.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                        "COALESCE(MAX(id), 0) + 1, false) FROM hr_ops.{}"
                    ).format(sql.Identifier(table)),
                    (f"hr_ops.{table}",),
                )
        pg_connection.commit()

        print("\nVerification")
        print("-" * 60)
        with mysql_connection.cursor() as mysql_cursor, pg_connection.cursor() as pg_cursor:
            for table in TABLES:
                mysql_rows, mysql_columns = fetch_mysql(mysql_connection, table)
                pg_rows, _ = fetch_postgres(pg_cursor, table)

                mysql_cursor.execute(f"SELECT COUNT(*) AS total FROM `{table}`")
                mysql_count = mysql_cursor.fetchone()["total"]
                pg_count = len(pg_rows)

                matches = mysql_count == pg_count and signature(
                    mysql_rows, mysql_columns
                ) == signature(pg_rows, mysql_columns)
                print(
                    f"{table:<24} mysql={mysql_count:<4} postgres={pg_count:<4} "
                    f"{'OK' if matches else 'MISMATCH'}"
                )
                if not matches:
                    failures.append(table)
    finally:
        mysql_connection.close()
        pg_connection.close()

    if failures:
        print(f"\nFAILED verification for: {', '.join(failures)}")
        return 1

    print(f"\nAll {len(TABLES)} tables migrated and verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

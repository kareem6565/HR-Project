"""Exercise the A5 Alembic upgrade and downgrade in an isolated local database."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND_DIR)


def _run_alembic(database_url: str, *args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        details = re.sub(
            r"(postgres(?:ql)?(?:\+\w+)?://)[^@\s]+@",
            r"\1[credentials-redacted]@",
            result.stderr,
        )
        raise RuntimeError(f"Alembic {args[0]} exited with {result.returncode}: {details[-1200:]}")


def main() -> int:
    from app.core.config import settings

    base_url = make_url(settings.database_url)
    if base_url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise RuntimeError("Migration verification requires the local PostgreSQL database.")
    if (base_url.host or "localhost").lower() not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Refusing migration verification against a non-local database host.")

    database_name = f"hera_a5_verify_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(
        base_url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    created = False
    engine = None
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database_name},
            )
            if exists:
                raise RuntimeError("Generated verification database already exists.")
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
            created = True

        target_url = base_url.set(database=database_name)
        target_database_url = target_url.render_as_string(hide_password=False)
        _run_alembic(target_database_url, "upgrade", "030_privacy_retention")
        _run_alembic(target_database_url, "upgrade", "head")

        engine = create_engine(target_url)
        expected = {
            "jobs": {"prerank_top_n"},
            "job_applications": {
                "advisory_rank",
                "advisory_score",
                "advisory_status",
                "advisory_message",
            },
            "screening_batch_items": {
                "advisory_rank",
                "advisory_score",
                "advisory_status",
                "advisory_message",
            },
        }
        inspector = inspect(engine)
        for table, expected_columns in expected.items():
            columns = {column["name"] for column in inspector.get_columns(table)}
            if not expected_columns <= columns:
                raise RuntimeError(f"Upgrade verification failed for {table}.")
        with engine.connect() as connection:
            upgraded_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if upgraded_revision != "031_a5_advisory_prerank":
            raise RuntimeError("Upgrade did not reach the A5 revision.")

        _run_alembic(target_database_url, "downgrade", "030_privacy_retention")
        inspector = inspect(engine)
        for table, a5_columns in expected.items():
            columns = {column["name"] for column in inspector.get_columns(table)}
            if a5_columns & columns:
                raise RuntimeError(f"Downgrade verification failed for {table}.")
        with engine.connect() as connection:
            downgraded_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if downgraded_revision != "030_privacy_retention":
            raise RuntimeError("Downgrade did not return to revision 030.")

        print("A5 upgrade: PASS (revision 031 and all expected columns verified).")
        print("A5 downgrade: PASS (revision 030 restored; A5 columns absent).")
        return 0
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": database_name},
                )
                connection.execute(text(f'DROP DATABASE "{database_name}"'))
            print("Temporary local verification database removed.")
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

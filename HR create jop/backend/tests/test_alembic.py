"""Ensure the migration chain resolves to exactly one head."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_single_alembic_head() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["035_merge_billing_pipeline"], f"Expected single head, got {heads}"


def test_pipeline_migration_backfills_and_downgrades_on_throwaway_sqlite() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    migration_path = backend_root / "alembic" / "versions" / "034_pipeline_stages.py"
    spec = importlib.util.spec_from_file_location("migration_034_test", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite://")
    organization_id, application_id, interview_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        metadata = sa.MetaData()
        organizations = sa.Table(
            "organizations", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True)
        )
        users = sa.Table(
            "users", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True)
        )
        applications = sa.Table(
            "job_applications",
            metadata,
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("resume_id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
        )
        interviews = sa.Table(
            "interviews",
            metadata,
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("job_application_id", sa.Uuid(as_uuid=True), nullable=False),
        )
        metadata.create_all(connection)
        connection.execute(organizations.insert(), [{"id": organization_id}])
        connection.execute(users.insert(), [{"id": uuid.uuid4()}])
        connection.execute(
            applications.insert(),
            [
                {
                    "id": application_id,
                    "organization_id": organization_id,
                    "job_id": uuid.uuid4(),
                    "candidate_id": uuid.uuid4(),
                    "resume_id": uuid.uuid4(),
                    "status": "advanced",
                },
            ],
        )
        connection.execute(
            interviews.insert(), [{"id": interview_id, "job_application_id": application_id}]
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        row = connection.execute(
            sa.text("SELECT pipeline_stage FROM job_applications WHERE id = :id"),
            {"id": application_id.hex},
        ).one()
        assert row.pipeline_stage == "interview"
        baseline = connection.execute(
            sa.text(
                "SELECT from_stage, to_stage, source, reason_code, created_at "
                "FROM pipeline_stage_transitions WHERE job_application_id = :id"
            ),
            {"id": application_id.hex},
        ).one()
        assert baseline.from_stage is None
        assert baseline.to_stage == "interview"
        assert baseline.source == "migration"
        assert baseline.reason_code == "migration_baseline"
        assert baseline.created_at

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        inspector = sa.inspect(connection)
        assert "pipeline_stage_transitions" not in inspector.get_table_names()
        assert "pipeline_stage" not in {
            column["name"] for column in inspector.get_columns("job_applications")
        }
    engine.dispose()


def test_pipeline_migration_dry_run_reports_stage_counts_without_writing(
    monkeypatch, capsys
) -> None:
    import sys

    from sqlalchemy.orm import Session, sessionmaker

    from tools import migrate_pipeline_stages

    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    applications = sa.Table(
        "job_applications",
        metadata,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(50), nullable=False),
    )
    interviews = sa.Table(
        "interviews",
        metadata,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_application_id", sa.Uuid(as_uuid=True), nullable=False),
    )
    metadata.create_all(engine)
    application_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(applications.insert(), [{"id": application_id, "status": "advanced"}])
    factory = sessionmaker(engine, class_=Session)
    monkeypatch.setattr(migrate_pipeline_stages, "SessionLocal", factory)
    monkeypatch.setattr(sys, "argv", ["migrate_pipeline_stages.py", "--dry-run"])

    assert migrate_pipeline_stages.main() == 0
    output = capsys.readouterr().out
    assert "review: 1" in output
    assert "total_mapped: 1" in output
    assert "dry_run: no changes written" in output
    with factory() as db:
        assert db.scalar(sa.select(applications.c.status)) == "advanced"
        assert db.scalar(sa.select(sa.func.count()).select_from(interviews)) == 0
    engine.dispose()

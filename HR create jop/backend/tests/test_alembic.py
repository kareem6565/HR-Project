"""Ensure the migration chain resolves to exactly one head."""

from __future__ import annotations

from pathlib import Path


def test_single_alembic_head() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["019_interview_portal"], f"Expected single head, got {heads}"

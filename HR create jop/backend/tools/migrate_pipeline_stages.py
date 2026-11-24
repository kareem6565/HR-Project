"""Read-only preflight for migration 034; prints mapped-stage counts only."""

from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import exists, select

from app.core.database import SessionLocal
from app.models import Interview, JobApplication


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="Required: this preflight never writes data.",
    )
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("Only --dry-run is supported.")

    mapped: Counter[str] = Counter()
    unknown: Counter[str] = Counter()
    statement = select(
        JobApplication.status,
        exists(select(1).where(Interview.job_application_id == JobApplication.id)).label(
            "has_interview"
        ),
    )
    with SessionLocal() as db:
        for status, has_interview in db.execute(statement):
            stage = {
                "created": "screening",
                "analysis_pending": "screening",
                "analyzing": "screening",
                "analysis_failed": "screening",
                "ready_for_review": "review",
                "hold": "interview" if has_interview else "review",
                "advanced": "interview" if has_interview else "review",
                "rejected": "rejected",
                "archived": "archived",
            }.get(status)
            if stage is None:
                unknown[status] += 1
            else:
                mapped[stage] += 1
    print("Pipeline stage backfill preflight (read-only)")
    for stage in ("screening", "review", "interview", "rejected", "archived"):
        print(f"{stage}: {mapped[stage]}")
    print(f"total_mapped: {sum(mapped.values())}")
    for status, count in sorted(unknown.items()):
        print(f"unmapped status {status!r}: {count}")
    if unknown:
        print("STOP: resolve unknown statuses before applying migration 034.")
        return 1
    print("dry_run: no changes written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

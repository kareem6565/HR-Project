from __future__ import annotations

import argparse
import json

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.candidate_privacy_service import CandidatePrivacyService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the disabled-by-default HERA retention job.")
    parser.add_argument("--dry-run", action="store_true", help="Report aggregate counts only.")
    parser.add_argument(
        "--apply", action="store_true", help="Apply deletion when retention is enabled."
    )
    parser.add_argument("--max-deletions", type=int, default=None)
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("Choose either --dry-run or --apply.")
    if not args.apply and not args.dry_run:
        args.dry_run = True
    if (
        args.max_deletions is not None
        and not 1 <= args.max_deletions <= settings.retention_max_deletions_per_run
    ):
        parser.error("--max-deletions must be between 1 and RETENTION_MAX_DELETIONS_PER_RUN.")

    db = SessionLocal()
    try:
        result = CandidatePrivacyService().run_retention(
            db, dry_run=args.dry_run, max_deletions=args.max_deletions
        )
        if args.apply:
            if not settings.retention_enabled:
                parser.error("Set RETENTION_ENABLED=true before applying retention deletions.")
            db.commit()
        else:
            db.rollback()
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import time

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.hr_sso_assertion_use import HRSSOAssertionUse

ASSERTION_CLOCK_SKEW_SECONDS = 5


def consume_assertion(db: Session, assertion_id: str, expires_at: int) -> bool:
    """Atomically consume a verified assertion identifier once."""
    now = int(time.time())
    db.execute(delete(HRSSOAssertionUse).where(HRSSOAssertionUse.expires_at <= now))
    identifier_hash = hashlib.sha256(assertion_id.encode("ascii")).hexdigest()
    try:
        with db.begin_nested():
            db.add(
                HRSSOAssertionUse(
                    jti_hash=identifier_hash,
                    expires_at=expires_at + ASSERTION_CLOCK_SKEW_SECONDS,
                )
            )
            db.flush()
    except IntegrityError:
        return False
    return True

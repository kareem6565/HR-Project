from __future__ import annotations

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HRSSOAssertionUse(Base):
    __tablename__ = "hr_sso_assertion_uses"
    __table_args__ = (Index("ix_hr_sso_assertion_uses_expires_at", "expires_at"),)

    jti_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

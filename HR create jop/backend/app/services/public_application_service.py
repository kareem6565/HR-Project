from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import case, delete, event, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Job, JobApplication, JobDistribution, PublicApplicationRateLimit
from app.services.candidate_service import CandidateService
from app.services.errors import InvalidStateError, NotFoundError, ValidationError
from app.services.job_application_service import JobApplicationService
from app.services.resume_service import ResumeService
from app.services.screening_batch_service import ScreeningBatchService
from app.services.storage_service import LocalFileSystemStorage

logger = logging.getLogger(__name__)


class PublicApplicationService:
    def __init__(self, *, resume_service: ResumeService | None = None) -> None:
        self.resume_service = resume_service or ResumeService()

    @staticmethod
    def privacy_notice_available() -> bool:
        configured = bool(
            settings.application_privacy_notice_text.strip()
            and settings.application_privacy_notice_version.strip()
        )
        if settings.app_env == "production":
            return configured and settings.application_privacy_notice_approved
        return configured

    @staticmethod
    def consume_rate_limit(db: Session, *, client_host: str | None) -> bool:
        """Atomically consume one per-IP fixed-window submission slot."""
        host = client_host or "unknown"
        fingerprint = hmac.new(
            settings.jwt_secret_key.encode(), host.encode(), hashlib.sha256
        ).hexdigest()
        now = datetime.now(UTC)
        window_seconds = max(1, settings.public_application_rate_window_seconds)
        reset_before = now - timedelta(seconds=window_seconds)
        bind = db.get_bind()
        engine = bind.engine if hasattr(bind, "engine") else bind
        test_database = settings.test_database_url.rsplit("/", 1)[-1]
        is_test_database = (
            settings.app_env == "test"
            or engine.url.database == test_database
            or (engine.dialect.name == "sqlite" and engine.url.database is None)
        )
        rate_db = db if is_test_database else Session(bind=engine)
        owns_session = rate_db is not db
        try:
            table = PublicApplicationRateLimit.__table__
            rate_db.execute(
                delete(table).where(table.c.window_started_at < now - timedelta(days=1))
            )
            dialect = rate_db.get_bind().dialect.name
            insert = pg_insert if dialect == "postgresql" else sqlite_insert
            statement = insert(table).values(
                fingerprint_hash=fingerprint,
                window_started_at=now,
                submission_count=1,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[table.c.fingerprint_hash],
                set_={
                    "window_started_at": case(
                        (table.c.window_started_at <= reset_before, now),
                        else_=table.c.window_started_at,
                    ),
                    "submission_count": case(
                        (table.c.window_started_at <= reset_before, 1),
                        else_=table.c.submission_count + 1,
                    ),
                },
            ).returning(table.c.submission_count)
            count = rate_db.scalar(statement)
            if owns_session:
                rate_db.commit()
            return int(count or 0) <= max(1, settings.public_application_rate_limit)
        except Exception:
            if owns_session:
                rate_db.rollback()
            raise
        finally:
            if owns_session:
                rate_db.close()

    def submit(
        self,
        db: Session,
        *,
        public_id: str,
        idempotency_key: str,
        full_name: str,
        email: str,
        phone: str | None,
        linkedin_url: str | None,
        github_url: str | None,
        portfolio_url: str | None,
        resume_filename: str,
        resume_content_type: str,
        resume_bytes: bytes,
        resume_checksum: str,
        privacy_accepted: bool,
        privacy_notice_version: str,
        turnstile_token: str | None,
        source: str | None,
        source_medium: str | None,
        source_campaign: str | None,
    ) -> tuple[str, bool]:
        self._ensure_privacy_config()
        self._validate_fields(
            full_name=full_name,
            email=email,
            phone=phone,
            linkedin_url=linkedin_url,
            github_url=github_url,
            portfolio_url=portfolio_url,
            privacy_accepted=privacy_accepted,
        )
        if privacy_notice_version != settings.application_privacy_notice_version:
            raise ValidationError("The application privacy notice has changed. Please review it.")
        if settings.turnstile_required and not self.verify_turnstile(turnstile_token):
            raise ValidationError("Bot verification failed. Please try again.")

        if not re.fullmatch(r"[A-Za-z0-9_-]{32}", public_id or ""):
            raise NotFoundError("Public job was not found.")
        job = db.scalar(select(Job).where(Job.public_id == public_id))
        if job is None or job.publication_status == "unpublished":
            raise NotFoundError("Public job was not found.")
        if job.publication_status != "published" or job.status != "active":
            raise InvalidStateError("This job is no longer accepting applications.")

        # A valid HERA campaign key is canonical; do not trust editable UTM
        # values supplied by the browser for campaign-attributed submissions.
        campaign = db.scalar(
            select(JobDistribution).where(
                JobDistribution.job_id == job.id,
                JobDistribution.organization_id == job.organization_id,
                JobDistribution.tracking_key == (source_campaign or ""),
            )
        )
        if campaign is not None:
            source = campaign.channel
            source_medium = {
                "linkedin": "social",
                "facebook": "social",
                "wuzzuf": "job_board",
                "other": "external",
            }[campaign.channel]
            source_campaign = campaign.tracking_key

        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        existing = db.scalar(
            select(JobApplication).where(
                JobApplication.organization_id == job.organization_id,
                JobApplication.job_id == job.id,
                JobApplication.idempotency_key_hash == key_hash,
            )
        )
        if existing is not None:
            return existing.public_reference or "", True

        normalized_email = email.strip()
        name = full_name.strip()
        storage = LocalFileSystemStorage(settings.storage_root_dir)
        resume = None
        try:
            with db.begin_nested():
                candidate = CandidateService().create(
                    db,
                    organization_id=job.organization_id,
                    full_name=name,
                    email=normalized_email.casefold(),
                    phone=(phone.strip() or None) if phone else None,
                )
                resume = self.resume_service.create_from_upload(
                    db,
                    candidate_id=candidate.id,
                    organization_id=job.organization_id,
                    filename=resume_filename,
                    content_type=resume_content_type,
                    file_bytes=resume_bytes,
                    max_upload_bytes=settings.max_upload_bytes,
                    storage=storage,
                    checksum=resume_checksum,
                )
                db.info["public_application_pending_file"] = (storage, resume.file_uri)
                application = JobApplicationService().create(
                    db,
                    organization_id=job.organization_id,
                    job_id=job.id,
                    candidate_id=candidate.id,
                    resume_id=resume.id,
                )
                application.public_reference = secrets.token_urlsafe(24)
                application.idempotency_key_hash = key_hash
                application.source = self._clean_attribution(source)
                application.source_medium = self._clean_attribution(source_medium)
                application.source_campaign = self._clean_attribution(source_campaign)
                application.linkedin_url = self._clean_optional(linkedin_url)
                application.github_url = self._clean_optional(github_url)
                application.portfolio_url = self._clean_optional(portfolio_url)
                application.privacy_notice_accepted = True
                application.privacy_notice_version = settings.application_privacy_notice_version
                application.privacy_notice_text = settings.application_privacy_notice_text
                application.privacy_notice_accepted_at = datetime.now(UTC)
                application.public_contact_email = normalized_email
                db.flush()
                ScreeningBatchService().schedule_public_application(
                    db, application=application, job=job, resume=resume
                )
        except IntegrityError:
            if resume is not None:
                storage.delete(file_uri=resume.file_uri)
            db.info.pop("public_application_pending_file", None)
            # A concurrent retry with the same client key may have committed first.
            existing = db.scalar(
                select(JobApplication).where(
                    JobApplication.organization_id == job.organization_id,
                    JobApplication.job_id == job.id,
                    JobApplication.idempotency_key_hash == key_hash,
                )
            )
            if existing is not None:
                return existing.public_reference or "", True
            raise
        except Exception:
            if resume is not None:
                storage.delete(file_uri=resume.file_uri)
            db.info.pop("public_application_pending_file", None)
            raise
        return application.public_reference, False

    @staticmethod
    def _ensure_privacy_config() -> None:
        if not PublicApplicationService.privacy_notice_available():
            raise InvalidStateError(
                "Applications are temporarily unavailable while the privacy notice is configured."
            )

    @staticmethod
    def _clean_attribution(value: str | None) -> str | None:
        if value is None:
            return None
        clean = " ".join(value.split())
        return clean.casefold()[:100] or None

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @classmethod
    def _validate_fields(
        cls,
        *,
        full_name: str,
        email: str,
        phone: str | None,
        linkedin_url: str | None,
        github_url: str | None,
        portfolio_url: str | None,
        privacy_accepted: bool,
    ) -> None:
        name = full_name.strip()
        if not 2 <= len(name) <= 255:
            raise ValidationError("Enter your full name (2 to 255 characters).")
        address = email.strip()
        email_pattern = (
            r"[^\s@]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
        )
        if len(address) > 255 or not re.fullmatch(email_pattern, address):
            raise ValidationError("Enter a valid email address.")
        if phone and len(phone.strip()) > 50:
            raise ValidationError("Phone number is too long.")
        if phone and not re.fullmatch(r"[+0-9().\-\s]{5,50}", phone.strip()):
            raise ValidationError("Enter a valid phone number.")
        cls._validate_profile_url(linkedin_url, "linkedin.com", r"/in/[^/]+/?")
        cls._validate_profile_url(github_url, "github.com", r"/[^/]+/?")
        if portfolio_url:
            parsed = urlsplit(portfolio_url.strip())
            hostname = (parsed.hostname or "").lower()
            if (
                parsed.scheme != "https"
                or not hostname
                or not parsed.netloc
                or len(portfolio_url) > 2048
                or hostname == "localhost"
                or hostname.endswith(".local")
                or "." not in hostname
                or not PublicApplicationService._public_literal_host(hostname)
                or parsed.port not in (None, 443)
            ):
                raise ValidationError("Portfolio links must be valid public HTTPS URLs.")
            if parsed.username or parsed.password:
                raise ValidationError("Portfolio URL must not contain credentials.")
        if not privacy_accepted:
            raise ValidationError("Please acknowledge the application privacy notice.")

    @staticmethod
    def _validate_profile_url(value: str | None, domain: str, path_pattern: str) -> None:
        if not value:
            return
        parsed = urlsplit(value.strip())
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or len(value) > 2048
            or hostname not in {domain, f"www.{domain}"}
            or not re.fullmatch(path_pattern, parsed.path)
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            label = "LinkedIn" if domain == "linkedin.com" else "GitHub"
            raise ValidationError(f"Enter a valid {label} profile URL.")

    @staticmethod
    def _public_literal_host(hostname: str) -> bool:
        try:
            return ipaddress.ip_address(hostname).is_global
        except ValueError:
            return True

    @staticmethod
    def verify_turnstile(token: str | None) -> bool:
        if not settings.turnstile_required:
            return True
        if not settings.turnstile_secret_key or not token:
            return False
        payload = urllib.parse.urlencode(
            {"secret": settings.turnstile_secret_key, "response": token}
        ).encode()
        request = urllib.request.Request(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                result = json.loads(response.read(16_384))
                if not result.get("success") or result.get("action") != "public_application":
                    return False
                expected_host = settings.turnstile_expected_hostname.strip().lower()
                actual_host = str(result.get("hostname", "")).lower()
                return not expected_host or actual_host == expected_host
        except (OSError, ValueError, TimeoutError):
            return False


@event.listens_for(Session, "after_rollback")
def _remove_uncommitted_public_resume(session: Session) -> None:
    if session.in_nested_transaction():
        return
    pending = session.info.pop("public_application_pending_file", None)
    if pending:
        storage, file_uri = pending
        storage.delete(file_uri=file_uri)


@event.listens_for(Session, "after_commit")
def _clear_committed_public_resume(session: Session) -> None:
    if session.in_nested_transaction():
        return
    session.info.pop("public_application_pending_file", None)

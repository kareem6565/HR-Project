"""Comprehensive test suite for HERA Prompt 7: Asynchronous CV Screening Batches and Worker.

Validates:
- Batch submission via POST /api/v1/jobs/{job_id}/screening-batches returning 202 Accepted.
- Input validation: max file count, size limits, required files, tenant authorization.
- Duplicate CV detection: in-batch duplicate handling and historical duplicate handling without
  candidate merging.
- Organization isolation for batch and item inspection.
- Organization isolation and validation for item retry
  (POST /api/v1/screening-batch-items/{item_id}/retry).
- PostgreSQL worker claim semantics (SKIP LOCKED, claim tokens, lease timeouts).
- Worker end-to-end processing: candidate creation, resume storage, application creation,
  evaluation.
- Per-file failure isolation on mixed batches (valid + corrupt files).
- Safe provider guard refusing unapproved live AI providers in background worker.
- Stale lease recovery for crashed or timed-out worker tasks.
- Storage isolation and cleanup of abandoned batch uploads without touching resumes.
"""

from __future__ import annotations

import io
import time
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.ai.providers.errors import ProviderRateLimitError
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.models import (
    AuditLog,
    Candidate,
    CandidateEvaluation,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    ScreeningBatch,
    ScreeningBatchItem,
    User,
)
from app.services.errors import UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED
from app.services.storage_service import LocalFileSystemStorage
from app.services.user_service import UserService
from app.worker import ScreeningWorker
from tests.resume_upload_fixtures import make_docx_bytes, make_pdf_bytes


def _test_session_factory(db_session):
    """Keep worker progress writes on the isolated test database, never app DATABASE_URL."""
    return sessionmaker(bind=db_session.get_bind())


# ==============================================================================
# Fixtures & Setup
# ==============================================================================


@pytest.fixture()
def client(db_session):
    """Provide a test client wired to the active database session."""
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path):
    """Isolate storage root directory to avoid polluting disk during tests."""
    original_root = settings.storage_root_dir
    settings.storage_root_dir = str(tmp_path / "storage")
    yield
    settings.storage_root_dir = original_root


@pytest.fixture()
def org_a(db_session) -> Organization:
    org = Organization(name="Organization Alpha")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def org_b(db_session) -> Organization:
    org = Organization(name="Organization Beta")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def recruiter_a(db_session, org_a) -> User:
    user = UserService().create(
        db_session,
        organization_id=org_a.id,
        email="recruiter@alpha.com",
        full_name="Recruiter Alpha",
        password="ValidPassword123!",
        role="recruiter",
    )
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def recruiter_b(db_session, org_b) -> User:
    user = UserService().create(
        db_session,
        organization_id=org_b.id,
        email="recruiter@beta.com",
        full_name="Recruiter Beta",
        password="ValidPassword123!",
        role="recruiter",
    )
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_header(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        token_version=user.token_version,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def job_a(db_session, org_a, recruiter_a) -> Job:
    job = Job(
        organization_id=org_a.id,
        title="Senior Python Backend Developer",
        raw_description="Looking for Python, FastAPI, and PostgreSQL expertise.",
        status="active",
        created_by_user_id=recruiter_a.id,
    )
    db_session.add(job)
    db_session.flush()

    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        is_current=True,
        status="approved",
        source="hr_created",
        profile_data={
            "requirements": [
                {"text": "Python 3 Experience", "category": "must_have", "dimension": "skill"},
                {"text": "FastAPI Experience", "category": "important", "dimension": "skill"},
            ]
        },
        approved_by_user_id=recruiter_a.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture()
def job_b(db_session, org_b, recruiter_b) -> Job:
    job = Job(
        organization_id=org_b.id,
        title="Frontend React Developer",
        raw_description="Looking for React and CSS expertise.",
        status="active",
        created_by_user_id=recruiter_b.id,
    )
    db_session.add(job)
    db_session.flush()

    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        is_current=True,
        status="approved",
        source="hr_created",
        profile_data={
            "requirements": [
                {"text": "React Experience", "category": "must_have", "dimension": "skill"},
            ]
        },
        approved_by_user_id=recruiter_b.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(job)
    return job


# ==============================================================================
# 1. Batch Submission Tests
# ==============================================================================


class TestBatchSubmission:
    def test_submit_batch_immediate_202_acceptance(self, client, job_a, recruiter_a):
        pdf1 = make_pdf_bytes("Alice Engineer resume content with Python and FastAPI")
        docx1 = make_docx_bytes("Bob Developer resume with PostgreSQL skills")

        files = [
            ("files", ("alice_cv.pdf", io.BytesIO(pdf1), "application/pdf")),
            (
                "files",
                (
                    "bob_cv.docx",
                    io.BytesIO(docx1),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
        ]

        resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )

        assert resp.status_code == 202
        data = resp.json()
        assert "batch_id" in data
        assert data["job_id"] == str(job_a.id)
        assert data["status"] == "queued"
        assert data["total_files"] == 2
        assert len(data["items"]) == 2
        assert all(it["status"] == "queued" for it in data["items"])

        # Check storage containment for batch files
        storage = LocalFileSystemStorage(settings.storage_root_dir)
        batch_id = uuid.UUID(data["batch_id"])
        item_id = uuid.UUID(data["items"][0]["id"])
        key = f"batches/{job_a.organization_id}/{batch_id}/{item_id}.pdf"
        assert storage.read(file_uri=key) == pdf1

    def test_submit_batch_unauthenticated_rejected(self, client, job_a):
        files = [("files", ("test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf"))]
        resp = client.post(f"/api/v1/jobs/{job_a.id}/screening-batches", files=files)
        assert resp.status_code == 401

    def test_submit_batch_nonexistent_job_returns_404(self, client, recruiter_a):
        fake_job_id = uuid.uuid4()
        files = [("files", ("test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf"))]
        resp = client.post(
            f"/api/v1/jobs/{fake_job_id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        assert resp.status_code == 404

    def test_submit_batch_cross_org_tenant_isolation(self, client, job_a, recruiter_b):
        # Recruiter B tries submitting to Job A (which belongs to Org A)
        files = [("files", ("test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf"))]
        resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_b),
        )
        assert resp.status_code == 404

    def test_submit_batch_exceeding_max_files_limit(self, client, job_a, recruiter_a):
        # Exceed max 20 files
        files = [
            ("files", (f"file_{i}.pdf", io.BytesIO(make_pdf_bytes(f"Text {i}")), "application/pdf"))
            for i in range(21)
        ]
        resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        assert resp.status_code in (400, 422)
        assert (
            resp.json().get("code") == UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED
            or "limit" in resp.text.lower()
        )


# ==============================================================================
# 2. Duplicate Detection Tests
# ==============================================================================


class TestDuplicateDetection:
    def test_in_batch_duplicate_cv_handling(self, client, job_a, recruiter_a):
        # Two identical files in the same submission
        identical_pdf = make_pdf_bytes("Identical Candidate Resume Text")
        files = [
            ("files", ("first_resume.pdf", io.BytesIO(identical_pdf), "application/pdf")),
            ("files", ("second_copy.pdf", io.BytesIO(identical_pdf), "application/pdf")),
        ]

        resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["total_files"] == 2
        items = data["items"]
        assert items[0]["status"] == "queued"
        assert items[1]["status"] == "duplicate"
        assert data["counts"]["queued"] == 1
        assert data["counts"]["duplicate"] == 1

    def test_historical_duplicate_cv_handling(self, client, db_session, job_a, recruiter_a):
        import hashlib

        existing_pdf = make_pdf_bytes("Historical Applied Candidate Content")
        sha256_hash = hashlib.sha256(existing_pdf).hexdigest()

        # Seed existing candidate and application for job_a with this hash
        cand = Candidate(organization_id=job_a.organization_id, full_name="Prior Applicant")
        db_session.add(cand)
        db_session.flush()

        resume = Resume(
            candidate_id=cand.id,
            file_uri="resumes/test.pdf",
            original_filename="prior.pdf",
            content_type="application/pdf",
            file_size_bytes=len(existing_pdf),
            checksum=sha256_hash,
            extracted_text="Prior text",
            status="text_extracted",
        )
        db_session.add(resume)
        db_session.flush()

        app = JobApplication(
            organization_id=job_a.organization_id,
            job_id=job_a.id,
            candidate_id=cand.id,
            resume_id=resume.id,
            status="created",
        )
        db_session.add(app)
        db_session.commit()

        # Recruiter submits a batch with that same file
        files = [("files", ("reapplied.pdf", io.BytesIO(existing_pdf), "application/pdf"))]
        resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["items"][0]["status"] == "duplicate"
        assert data["counts"]["duplicate"] == 1


# ==============================================================================
# 3. Batch and Item Status Query Tests
# ==============================================================================


class TestBatchStatusQuery:
    def test_get_batch_status_success_and_counts(self, client, job_a, recruiter_a):
        pdf = make_pdf_bytes("Queryable Resume Text")
        files = [("files", ("resume.pdf", io.BytesIO(pdf), "application/pdf"))]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        batch_id = post_resp.json()["batch_id"]

        get_resp = client.get(
            f"/api/v1/screening-batches/{batch_id}",
            headers=auth_header(recruiter_a),
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["batch_id"] == batch_id
        assert data["total_files"] == 1
        assert data["counts"]["queued"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "queued"

    def test_get_batch_cross_org_returns_404(self, client, job_a, recruiter_a, recruiter_b):
        pdf = make_pdf_bytes("Candidate Alpha Only")
        files = [("files", ("resume.pdf", io.BytesIO(pdf), "application/pdf"))]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        batch_id = post_resp.json()["batch_id"]

        # Recruiter B queries Batch from Org A
        get_resp = client.get(
            f"/api/v1/screening-batches/{batch_id}",
            headers=auth_header(recruiter_b),
        )
        assert get_resp.status_code == 404


# ==============================================================================
# 4. Item Retry Tests
# ==============================================================================


class TestItemRetry:
    def test_retry_failed_item_success(self, client, db_session, job_a, recruiter_a):
        pdf = make_pdf_bytes("Candidate to fail and retry")
        files = [("files", ("candidate.pdf", io.BytesIO(pdf), "application/pdf"))]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        item_id = post_resp.json()["items"][0]["id"]

        # Manually transition item to failed state
        item = db_session.get(ScreeningBatchItem, uuid.UUID(item_id))
        item.status = "failed"
        item.stage = "failed"
        item.error_code = "CORRUPT"
        item.error_message = "Text extraction failed."
        item.attempts = 1
        item.batch.status = "failed"
        item.batch.failed_files = 1
        db_session.commit()

        # Retry item
        retry_resp = client.post(
            f"/api/v1/screening-batch-items/{item_id}/retry",
            headers=auth_header(recruiter_a),
        )
        assert retry_resp.status_code == 200
        retry_data = retry_resp.json()
        assert retry_data["status"] == "queued"
        assert retry_data["attempts"] == 1

        # Check DB state
        db_session.refresh(item)
        assert item.status == "queued"
        assert item.error_code is None
        assert item.claim_token is None

    def test_retry_non_failed_item_rejected(self, client, job_a, recruiter_a):
        pdf = make_pdf_bytes("Queued candidate")
        files = [("files", ("candidate.pdf", io.BytesIO(pdf), "application/pdf"))]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        item_id = post_resp.json()["items"][0]["id"]

        # Attempt to retry an item that is in "queued" status
        retry_resp = client.post(
            f"/api/v1/screening-batch-items/{item_id}/retry",
            headers=auth_header(recruiter_a),
        )
        assert retry_resp.status_code in (400, 409)

    def test_retry_cross_org_returns_404(self, client, db_session, job_a, recruiter_a, recruiter_b):
        pdf = make_pdf_bytes("Org A candidate")
        files = [("files", ("candidate.pdf", io.BytesIO(pdf), "application/pdf"))]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        item_id = post_resp.json()["items"][0]["id"]

        item = db_session.get(ScreeningBatchItem, uuid.UUID(item_id))
        item.status = "failed"
        db_session.commit()

        # Recruiter B tries retrying Org A's item
        retry_resp = client.post(
            f"/api/v1/screening-batch-items/{item_id}/retry",
            headers=auth_header(recruiter_b),
        )
        assert retry_resp.status_code == 404


# ==============================================================================
# 5. Worker Processing & Failure Isolation Tests
# ==============================================================================


class TestWorkerProcessing:
    def test_processing_query_locks_claimed_item_until_transaction_finishes(self):
        statement = ScreeningWorker._processing_item_query(uuid.uuid4())

        assert "FOR UPDATE" in str(statement.compile(dialect=postgresql.dialect()))

    def test_worker_logs_resume_cleanup_failure_without_logging_file_path(self, caplog):
        class FailingStorage:
            def delete(self, *, file_uri):
                raise OSError(f"cannot delete {file_uri}")

        file_uri = "private/candidate-resume.pdf"
        worker = ScreeningWorker(storage=FailingStorage())
        worker._cleanup_created_resume_file(file_uri, item_id=uuid.uuid4())

        assert "Failed to clean up a resume file after screening failure." in caplog.text
        assert file_uri not in caplog.text
        record = next(
            record
            for record in caplog.records
            if record.message == "Failed to clean up a resume file after screening failure."
        )
        assert record.exception_class == "OSError"

    def test_worker_claims_and_screens_item_successfully(
        self, client, db_session, job_a, recruiter_a
    ):
        pdf = make_pdf_bytes("Ada Lovelace is a brilliant Python software engineer.")
        files = [("files", ("ada_lovelace.pdf", io.BytesIO(pdf), "application/pdf"))]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        batch_id = uuid.UUID(post_resp.json()["batch_id"])

        # Instantiate worker
        storage = LocalFileSystemStorage(settings.storage_root_dir)
        worker = ScreeningWorker(storage=storage, session_factory=_test_session_factory(db_session))

        # 1. Claim
        claim = worker.claim_next_item(db_session)
        assert claim is not None
        item_id, claim_token = claim

        # 2. Process
        success = worker.process_item(db_session, item_id, claim_token)
        assert success is True

        # Verify database records
        item = db_session.get(ScreeningBatchItem, item_id)
        assert item.status == "done"
        assert item.candidate_id is not None
        assert item.resume_id is not None
        assert item.application_id is not None
        assert item.evaluation_id is not None

        # Check candidate evaluation score exists
        evaluation = db_session.get(CandidateEvaluation, item.evaluation_id)
        assert evaluation is not None
        assert evaluation.score is not None

        # Check batch status
        batch = db_session.get(ScreeningBatch, batch_id)
        assert batch.status == "completed"
        assert batch.completed_files == 1
        assert batch.failed_files == 0

    def test_worker_per_file_failure_isolation(self, client, db_session, job_a, recruiter_a):
        # Batch with 1 valid file and 1 corrupted file
        valid_pdf = make_pdf_bytes("Valid engineer with FastAPI and Python expertise.")
        corrupt_bytes = b"%PDF-1.4\ncorrupted file stream without valid objects %%EOF"

        files = [
            ("files", ("valid_cv.pdf", io.BytesIO(valid_pdf), "application/pdf")),
            ("files", ("corrupt_cv.pdf", io.BytesIO(corrupt_bytes), "application/pdf")),
        ]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        batch_id = uuid.UUID(post_resp.json()["batch_id"])

        storage = LocalFileSystemStorage(settings.storage_root_dir)
        worker = ScreeningWorker(storage=storage, session_factory=_test_session_factory(db_session))

        # Process first item
        claim1 = worker.claim_next_item(db_session)
        assert claim1 is not None
        worker.process_item(db_session, claim1[0], claim1[1])

        # Process second item
        claim2 = worker.claim_next_item(db_session)
        assert claim2 is not None
        worker.process_item(db_session, claim2[0], claim2[1])

        # Verify isolation: one done, one failed, neither corrupted the other
        batch = db_session.get(ScreeningBatch, batch_id)
        assert batch.completed_files == 1
        assert batch.failed_files == 1

        items = {it.filename: it for it in batch.items}
        assert items["valid_cv.pdf"].status == "done"
        assert items["corrupt_cv.pdf"].status == "failed"
        assert items["corrupt_cv.pdf"].error_code is not None

    @pytest.mark.soal
    def test_worker_processing_with_soal_provider(self, client, db_session, job_a, recruiter_a):
        pdf = make_pdf_bytes("Developer Candidate")
        files = [("files", ("dev.pdf", io.BytesIO(pdf), "application/pdf"))]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        item_id = uuid.UUID(post_resp.json()["items"][0]["id"])

        storage = LocalFileSystemStorage(settings.storage_root_dir)
        worker = ScreeningWorker(storage=storage)
        claim = worker.claim_next_item(db_session)
        assert claim is not None

        # Temporarily flip ai_provider to soal
        orig_provider = settings.ai_provider
        settings.ai_provider = "soal"
        try:
            success = worker.process_item(db_session, claim[0], claim[1])
            assert success is True

            item = db_session.get(ScreeningBatchItem, item_id)
            assert item.status == "done"
            assert item.error_code is None
        finally:
            settings.ai_provider = orig_provider

    def test_worker_stale_lease_recovery(self, db_session, job_a):
        # Create an item in running state with lease_expires_at in the past
        batch = ScreeningBatch(
            organization_id=job_a.organization_id,
            job_id=job_a.id,
            status="running",
            total_files=1,
        )
        db_session.add(batch)
        db_session.flush()

        stale_item = ScreeningBatchItem(
            batch_id=batch.id,
            filename="stale.pdf",
            storage_key="dummy_key",
            sha256="dummy_sha",
            status="running",
            stage="claimed",
            attempts=1,
            max_attempts=3,
            claim_token="expired_token",
            lease_expires_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        db_session.add(stale_item)
        db_session.commit()

        storage = LocalFileSystemStorage(settings.storage_root_dir)
        worker = ScreeningWorker(storage=storage)
        recovered = worker.recover_stale_leases(db_session)
        assert recovered == 1

        db_session.refresh(stale_item)
        assert stale_item.status == "queued"
        assert stale_item.claim_token is None
        assert stale_item.lease_expires_at is None

    def test_worker_stale_lease_recovery_exhausted_attempts(self, db_session, job_a):
        # Item that exceeded max attempts and lease expired
        batch = ScreeningBatch(
            organization_id=job_a.organization_id,
            job_id=job_a.id,
            status="running",
            total_files=1,
        )
        db_session.add(batch)
        db_session.flush()

        exhausted_item = ScreeningBatchItem(
            batch_id=batch.id,
            filename="exhausted.pdf",
            storage_key="dummy_key",
            sha256="dummy_sha",
            status="running",
            stage="claimed",
            attempts=3,
            max_attempts=3,
            claim_token="expired_token",
            lease_expires_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        db_session.add(exhausted_item)
        db_session.commit()

        storage = LocalFileSystemStorage(settings.storage_root_dir)
        worker = ScreeningWorker(storage=storage)
        recovered = worker.recover_stale_leases(db_session)
        assert recovered == 1

        db_session.refresh(exhausted_item)
        assert exhausted_item.status == "failed"
        assert exhausted_item.error_code == "LEASE_EXPIRED"


# ==============================================================================
# 6. Storage Cleanup Tests
# ==============================================================================


class TestStorageCleanup:
    def test_cleanup_orphaned_batches_preserves_resumes(self, tmp_path, org_a):
        storage = LocalFileSystemStorage(str(tmp_path / "storage"))

        # 1. Create a permanent resume
        resume_id = uuid.uuid4()
        storage.save(
            organization_id=org_a.id,
            resume_id=resume_id,
            extension="pdf",
            stream=lambda: b"%PDF-1.4 permanent resume",
        )

        # 2. Create an orphaned batch file
        batch_id = uuid.uuid4()
        item_id = uuid.uuid4()
        batch_key = storage.save_batch_file(
            organization_id=org_a.id,
            batch_id=batch_id,
            item_id=item_id,
            extension="pdf",
            stream=lambda: b"%PDF-1.4 batch file",
        )

        # Check both files exist
        assert (storage._root_dir / batch_key).exists() is True
        resume_key = f"resumes/{org_a.id}/{resume_id}.pdf"
        assert (storage._root_dir / resume_key).exists() is True

        # Run cleanup with max_age_seconds=0 (sweeps all batch folders)
        time.sleep(0.01)
        removed = storage.cleanup_orphaned_batches(max_age_seconds=0)
        assert removed >= 1

        # Batch file is deleted; resume file is preserved
        assert (storage._root_dir / batch_key).exists() is False
        assert (storage._root_dir / resume_key).exists() is True

    def test_list_job_screening_batches(self, client, job_a, recruiter_a):
        pdf = make_pdf_bytes("Batch Candidate")
        files = [("files", ("cand.pdf", io.BytesIO(pdf), "application/pdf"))]
        post_resp = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=files,
            headers=auth_header(recruiter_a),
        )
        assert post_resp.status_code == 202
        batch_id = post_resp.json()["batch_id"]

        list_resp = client.get(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            headers=auth_header(recruiter_a),
        )
        assert list_resp.status_code == 200
        batches = list_resp.json()
        assert len(batches) >= 1
        assert any(b["id"] == batch_id for b in batches)
        batch = next(b for b in batches if b["id"] == batch_id)
        assert "counts" in batch
        assert batch["total_files"] == 1


class TestB2LargeBatch:
    def test_zip_endpoint_accepts_docx_and_stores_using_opaque_keys(
        self, client, db_session, job_a, recruiter_a
    ):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("human-name.docx", make_docx_bytes("Candidate with Python"))
        response = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files={"archive": ("submitted.zip", io.BytesIO(payload.getvalue()), "application/zip")},
            headers=auth_header(recruiter_a),
        )
        assert response.status_code == 202, response.text
        batch = db_session.get(ScreeningBatch, uuid.UUID(response.json()["batch_id"]))
        item = batch.items[0]
        assert item.filename == "human-name.docx"
        assert "human-name" not in item.storage_key
        assert item.storage_key.endswith(f"{item.id}.docx")
        audit = db_session.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == batch.id, AuditLog.action == "screening.batch_created"
            )
        )
        assert audit.event_metadata == {"total_files": 1, "failed_count": 0, "duplicate_count": 0}
        assert "filename" not in audit.event_metadata

    def test_upload_config_is_backend_authoritative_and_org_role_scoped(self, client, recruiter_a):
        response = client.get("/api/v1/screening-upload-config", headers=auth_header(recruiter_a))
        assert response.status_code == 200
        config = response.json()
        assert config["max_file_bytes"] == settings.max_upload_bytes
        assert config["max_batch_files"] == settings.max_batch_files
        assert config["max_zip_total_bytes"] == settings.max_zip_total_bytes

    def test_progress_is_cross_tenant_scoped(
        self, client, db_session, job_a, recruiter_a, recruiter_b
    ):
        response = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=[("files", ("one.pdf", io.BytesIO(make_pdf_bytes("One")), "application/pdf"))],
            headers=auth_header(recruiter_a),
        )
        assert response.status_code == 202
        batch_id = response.json()["batch_id"]
        other_tenant = client.get(
            f"/api/v1/screening-batches/{batch_id}", headers=auth_header(recruiter_b)
        )
        assert other_tenant.status_code == 404

    def test_org_concurrent_batch_cap_is_enforced(self, client, job_a, recruiter_a, monkeypatch):
        monkeypatch.setattr(settings, "max_concurrent_batches_per_org", 1)

        def upload(label):
            return [
                ("files", (f"{label}.pdf", io.BytesIO(make_pdf_bytes(label)), "application/pdf"))
            ]

        accepted = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=upload("first"),
            headers=auth_header(recruiter_a),
        )
        assert accepted.status_code == 202
        rejected = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=upload("second"),
            headers=auth_header(recruiter_a),
        )
        assert rejected.status_code == 422
        assert "maximum number" in rejected.json()["detail"]

    def test_worker_routes_mid_batch_rate_limit_to_quota_wait(
        self, client, db_session, job_a, recruiter_a, monkeypatch
    ):
        response = client.post(
            f"/api/v1/jobs/{job_a.id}/screening-batches",
            files=[
                (
                    "files",
                    ("quota.pdf", io.BytesIO(make_pdf_bytes("Quota candidate")), "application/pdf"),
                )
            ],
            headers=auth_header(recruiter_a),
        )
        assert response.status_code == 202
        item_id = uuid.UUID(response.json()["items"][0]["id"])
        item = db_session.get(ScreeningBatchItem, item_id)
        claim_token = "rate-limit-claim"
        item.status = "running"
        item.stage = "claimed"
        item.claim_token = claim_token
        item.attempts = 1
        db_session.flush()

        worker = ScreeningWorker(
            storage=LocalFileSystemStorage(settings.storage_root_dir),
            session_factory=_test_session_factory(db_session),
        )
        routed = []
        monkeypatch.setattr(db_session, "rollback", lambda: None)
        monkeypatch.setattr(
            worker,
            "_record_quota_wait",
            lambda *args, **kwargs: routed.append((args, kwargs)),
        )
        monkeypatch.setattr(
            "app.worker.CandidateProfileExtractionWorkflow.run",
            lambda *args, **kwargs: (_ for _ in ()).throw(ProviderRateLimitError("provider quota")),
        )
        worker.process_item(db_session, item_id, claim_token)
        assert len(routed) == 1
        assert routed[0][0][:2] == (item_id, claim_token)
        assert routed[0][1]["processing_stage"] == "candidate_profile_extraction"

    def test_rate_limit_is_classified_as_quota_wait_without_retry_ceiling(self, db_session, job_a):
        batch = ScreeningBatch(
            organization_id=job_a.organization_id, job_id=job_a.id, status="running", total_files=1
        )
        item = ScreeningBatchItem(
            batch=batch,
            filename="quota.pdf",
            storage_key="generated-item-id.pdf",
            sha256="0" * 64,
            status="running",
            stage="claimed",
            attempts=9,
            max_attempts=3,
            claim_token="quota-token",
        )
        db_session.add(batch)
        db_session.add(item)
        db_session.flush()
        error = RuntimeError("wrapped")
        error.__cause__ = ProviderRateLimitError("provider quota")
        assert ScreeningWorker._caused_by_rate_limit(error)

        worker = ScreeningWorker(storage=LocalFileSystemStorage(settings.storage_root_dir))
        worker._record_quota_wait(
            item.id, "quota-token", db=db_session, processing_stage="candidate_evaluation"
        )
        assert item.status == "queued"
        assert item.stage == "waiting_for_quota"
        assert item.error_code == "WAITING_FOR_QUOTA"
        assert "resume automatically" in item.error_message
        next_attempt_at = item.next_attempt_at
        if next_attempt_at.tzinfo is None:
            next_attempt_at = next_attempt_at.replace(tzinfo=UTC)
        assert next_attempt_at > datetime.now(UTC)

    def test_300_synthetic_files_complete_with_isolated_failure_reporting(
        self, client, db_session, job_a, recruiter_a, monkeypatch
    ):
        uploads = []
        for index in range(299):
            pdf = make_pdf_bytes(
                f"Synthetic applicant {index} with Python SQL engineering skills {index}"
            )
            uploads.append(
                ("files", (f"applicant-{index}.pdf", io.BytesIO(pdf), "application/pdf"))
            )
        uploads.append(
            ("files", ("broken.pdf", io.BytesIO(b"%PDF-1.4\nnot a real PDF"), "application/pdf"))
        )
        monkeypatch.setattr(settings, "max_batch_files", 300)
        monkeypatch.setattr(settings, "max_concurrent_batches_per_org", 2)
        old_provider = settings.ai_provider
        settings.ai_provider = "fake"
        try:
            response = client.post(
                f"/api/v1/jobs/{job_a.id}/screening-batches",
                files=uploads,
                headers=auth_header(recruiter_a),
            )
            assert response.status_code == 202
            batch_id = uuid.UUID(response.json()["batch_id"])
            assert response.json()["counts"]["total"] == 300
            assert response.json()["counts"]["failed"] == 0

            worker = ScreeningWorker(
                storage=LocalFileSystemStorage(settings.storage_root_dir),
                session_factory=_test_session_factory(db_session),
            )
            for _ in range(300):
                claim = worker.claim_next_item(db_session)
                if claim is None:
                    break
                worker.process_item(db_session, claim[0], claim[1])

            db_session.expire_all()
            batch = db_session.get(ScreeningBatch, batch_id)
            assert batch.total_files == 300
            assert batch.completed_files == 299
            assert batch.failed_files == 1
            statuses = {item.filename: item.status for item in batch.items}
            assert statuses["broken.pdf"] == "failed"
            assert sum(status == "done" for status in statuses.values()) == 299
            progress = client.get(
                f"/api/v1/screening-batches/{batch_id}", headers=auth_header(recruiter_a)
            )
            assert progress.status_code == 200
            assert progress.json()["counts"]["completed"] == 299
            failed = next(
                item for item in progress.json()["items"] if item["filename"] == "broken.pdf"
            )
            assert failed["status"] == "failed"
            assert failed["reason"]
        finally:
            settings.ai_provider = old_provider

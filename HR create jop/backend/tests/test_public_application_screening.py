from __future__ import annotations

import hashlib
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

from app.models import Candidate, Job, JobApplication, JobProfile, Resume, ScreeningBatchItem
from app.services.screening_batch_service import ScreeningBatchService
from app.worker import ScreeningWorker
import app.worker as worker_module


def test_public_application_worker_reuses_records_and_pinned_profile(monkeypatch) -> None:
    organization_id = uuid.uuid4()
    job_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    application_id = uuid.uuid4()
    batch_id = uuid.uuid4()
    item_id = uuid.uuid4()
    claim_token = "public-claim-token"
    file_bytes = b"private public-application resume"
    profile = SimpleNamespace(id=profile_id, job_id=job_id, status="superseded", profile_data={"requirements": []})
    job = SimpleNamespace(id=job_id, organization_id=organization_id, title="Engineer")
    candidate = SimpleNamespace(
        id=candidate_id, organization_id=organization_id, full_name="Alex Candidate"
    )
    resume = SimpleNamespace(
        id=resume_id,
        candidate_id=candidate_id,
        file_uri="private/resume.pdf",
        extracted_text="Candidate CV text",
    )
    application = SimpleNamespace(
        id=application_id,
        organization_id=organization_id,
        job_id=job_id,
        candidate_id=candidate_id,
        resume_id=resume_id,
    )
    batch = SimpleNamespace(
        id=batch_id,
        organization_id=organization_id,
        job_id=job_id,
        status="running",
    )
    item = SimpleNamespace(
        id=item_id,
        batch_id=batch_id,
        batch=batch,
        filename="resume.pdf",
        storage_key=resume.file_uri,
        sha256=hashlib.sha256(file_bytes).hexdigest(),
        source="public_application",
        job_profile_id=profile_id,
        candidate_id=candidate_id,
        resume_id=resume_id,
        application_id=application_id,
        status="running",
        stage="claimed",
        attempts=1,
        max_attempts=3,
        claim_token=claim_token,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        error_code=None,
        error_message=None,
    )

    class FakeStorage:
        def read(self, *, file_uri):
            assert file_uri == resume.file_uri
            return file_bytes

    class FakeSession:
        def get(self, model, record_id):
            records = {
                ScreeningBatchItem: item,
                Job: job,
                JobProfile: profile,
                JobApplication: application,
                Resume: resume,
                Candidate: candidate,
            }
            return records[model]

        def begin_nested(self):
            return nullcontext()

        def commit(self):
            pass

        def rollback(self):
            raise AssertionError("Successful public screening must not roll back.")

    class FakeProfileWorkflow:
        def __init__(self, provider):
            pass

        def run(self, *args, **kwargs):
            assert kwargs["resume_id"] == resume_id

    class FakeEvaluationWorkflow:
        def __init__(self, **kwargs):
            pass

        def run(self, db, **kwargs):
            assert kwargs["job_application_id"] == application_id
            assert kwargs["job_profile_id"] == profile_id
            return SimpleNamespace(evaluation_id=uuid.uuid4())

    monkeypatch.setattr(worker_module, "extract_text", lambda *args, **kwargs: "CV text")
    monkeypatch.setattr(
        worker_module, "derive_screening_payloads", lambda **kwargs: ("profile", "evidence", "explanation")
    )
    monkeypatch.setattr(worker_module, "get_provider", lambda *args, **kwargs: object())
    monkeypatch.setattr(worker_module, "CandidateProfileExtractionWorkflow", FakeProfileWorkflow)
    monkeypatch.setattr(worker_module, "CandidateEvaluationWorkflow", FakeEvaluationWorkflow)
    monkeypatch.setattr(ScreeningBatchService, "_update_batch_state", lambda batch: None)
    monkeypatch.setattr(
        worker_module, "CandidateService",
        lambda: (_ for _ in ()).throw(AssertionError("Public applications must reuse candidates.")),
    )
    monkeypatch.setattr(
        worker_module, "JobApplicationService",
        lambda: (_ for _ in ()).throw(AssertionError("Public applications must reuse applications.")),
    )

    succeeded = ScreeningWorker(storage=FakeStorage()).process_item(
        FakeSession(), item_id, claim_token
    )

    assert succeeded is True
    assert item.status == "done"
    assert item.candidate_id == candidate_id
    assert item.resume_id == resume_id
    assert item.application_id == application_id
    assert item.evaluation_id is not None

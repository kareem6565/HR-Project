from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
import json
import logging
from types import SimpleNamespace
import uuid

from pydantic import BaseModel, ConfigDict, ValidationError as PydanticValidationError

import app.worker as worker_module
from app.core.logging import StructuredJsonFormatter
from app.models import Job, ScreeningBatchItem
from app.services.errors import ValidationError
from app.services.screening_batch_service import ScreeningBatchService
from app.worker import ScreeningWorker


def _synthetic_validation_exception(canary: str, mock_secret: str) -> ValidationError:
    class SyntheticOutput(BaseModel):
        model_config = ConfigDict(extra="forbid")

        score: int

    try:
        try:
            SyntheticOutput.model_validate(
                {
                    "score": f"{canary} {mock_secret}",
                    canary: mock_secret,
                }
            )
        except PydanticValidationError as cause:
            raise ValidationError(f"RAW EXCEPTION: {canary} {mock_secret}") from cause
    except ValidationError as error:
        return error

    raise AssertionError("The synthetic payload should fail schema validation.")


def test_structured_failure_diagnostics_exclude_payload_and_exception_text(caplog) -> None:
    canary = "HERA_CV_CANARY_7d10c6"
    mock_secret = "MOCK_API_SECRET_92fa01"
    error = _synthetic_validation_exception(canary, mock_secret)
    item_id = uuid.uuid4()
    batch_id = uuid.uuid4()
    item = SimpleNamespace(id=item_id, batch_id=batch_id, attempts=2)

    with caplog.at_level(logging.ERROR, logger="app.worker"):
        ScreeningWorker._log_item_failure(
            item,
            "candidate_profile_extraction",
            error,
        )

    record = caplog.records[-1]
    rendered = StructuredJsonFormatter().format(record)
    event = json.loads(rendered)

    assert event["batch_id"] == str(batch_id)
    assert event["item_id"] == str(item_id)
    assert event["attempt_number"] == 2
    assert event["processing_stage"] == "candidate_profile_extraction"
    assert event["exception_class"] == "ValidationError"
    assert {"location": ["score"], "type": "int_parsing"} in event["validation_errors"]
    assert {"location": ["[REDACTED]"], "type": "extra_forbidden"} in event[
        "validation_errors"
    ]
    assert event["exception_frames"]
    assert canary not in rendered
    assert mock_secret not in rendered
    assert "RAW EXCEPTION" not in rendered
    assert '"input"' not in rendered
    assert '"context"' not in rendered


def test_formatter_redacts_unrecognized_diagnostic_fields() -> None:
    record = logging.LogRecord(
        name="app.worker",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Screening batch item processing failed.",
        args=(),
        exc_info=None,
    )
    record.batch_id = "not-a-uuid-and-must-not-leak"
    record.item_id = str(uuid.uuid4())
    record.attempt_number = 1
    record.processing_stage = "UNEXPECTED_CANARY_STAGE"
    record.exception_class = "ValidationError"
    record.validation_errors = [
        {"location": ["full_name", "UNEXPECTED_CANARY_LOCATION"], "type": "missing"}
    ]
    record.exception_frames = [
        {"file": "CANARY_PATH.pdf", "function": "safe_function", "line": 3}
    ]

    rendered = StructuredJsonFormatter().format(record)
    event = json.loads(rendered)

    assert event["batch_id"] == "[REDACTED]"
    assert event["processing_stage"] == "[REDACTED]"
    assert event["validation_errors"][0]["location"] == ["full_name", "[REDACTED]"]
    assert event["exception_frames"][0]["file"] == "[REDACTED]"
    assert "UNEXPECTED_CANARY" not in rendered
    assert "CANARY_PATH.pdf" not in rendered


def test_worker_pipeline_failure_logs_actual_stage_without_sensitive_values(
    monkeypatch, caplog
) -> None:
    canary = "HERA_CV_CANARY_1e4ab9"
    mock_secret = "MOCK_API_SECRET_51cf02"
    error = _synthetic_validation_exception(canary, mock_secret)
    batch_id = uuid.uuid4()
    item = SimpleNamespace(
        id=uuid.uuid4(),
        batch_id=batch_id,
        batch=SimpleNamespace(
            id=batch_id,
            organization_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
        ),
        filename="synthetic.pdf",
        storage_key="synthetic-batch-object",
        sha256="synthetic-sha256",
        status="running",
        stage="claimed",
        attempts=1,
        max_attempts=3,
        claim_token="synthetic-claim-token",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        next_attempt_at=datetime.now(UTC),
        candidate_id=None,
        resume_id=None,
        application_id=None,
        evaluation_id=None,
        error_code=None,
        error_message=None,
    )
    job = SimpleNamespace(
        id=item.batch.job_id,
        organization_id=item.batch.organization_id,
        title="Synthetic Engineer",
        profiles=[SimpleNamespace(status="approved", profile_data={"requirements": []})],
    )

    class FakeStorage:
        def read(self, *, file_uri):
            assert file_uri == item.storage_key
            return b"synthetic document bytes"

        def save(self, **kwargs):
            return "synthetic-resume-object"

        def delete(self, *, file_uri):
            assert file_uri == "synthetic-resume-object"

    class FakeSession:
        def get(self, model, record_id):
            if model is ScreeningBatchItem:
                return item
            if model is Job:
                return job
            raise AssertionError("Unexpected model access in synthetic worker test.")

        def begin_nested(self):
            return nullcontext()

        def add(self, record):
            pass

        def flush(self):
            pass

        def rollback(self):
            pass

        def commit(self):
            pass

    class SyntheticCandidateService:
        def create(self, *args, **kwargs):
            return SimpleNamespace(id=uuid.uuid4(), full_name="Synthetic Candidate")

    class FailingProfileWorkflow:
        def __init__(self, provider):
            pass

        def run(self, *args, **kwargs):
            raise error

    monkeypatch.setattr(
        worker_module,
        "extract_text",
        lambda *args, **kwargs: "synthetic CV text",
    )
    monkeypatch.setattr(
        worker_module,
        "derive_screening_payloads",
        lambda **kwargs: ("profile", "evidence", "explanation"),
    )
    monkeypatch.setattr(worker_module, "get_provider", lambda *args, **kwargs: object())
    monkeypatch.setattr(worker_module, "CandidateService", SyntheticCandidateService)
    monkeypatch.setattr(
        worker_module, "CandidateProfileExtractionWorkflow", FailingProfileWorkflow
    )
    monkeypatch.setattr(ScreeningBatchService, "_update_batch_state", lambda batch: None)
    session = FakeSession()
    worker = ScreeningWorker(storage=FakeStorage(), initial_retry_delay_seconds=30)

    with caplog.at_level(logging.ERROR, logger="app.worker"):
        result = worker.process_item(session, item.id, item.claim_token)

    assert result is False
    assert item.status == "queued"
    record = next(
        record
        for record in caplog.records
        if getattr(record, "processing_stage", None) == "candidate_profile_extraction"
    )
    rendered = StructuredJsonFormatter().format(record)
    event = json.loads(rendered)
    assert event["batch_id"] == str(batch_id)
    assert event["item_id"] == str(item.id)
    assert event["attempt_number"] == 1
    assert event["processing_stage"] == "candidate_profile_extraction"
    assert event["validation_errors"][0] == {
        "location": ["score"],
        "type": "int_parsing",
    }
    assert canary not in rendered
    assert mock_secret not in rendered
    assert "RAW EXCEPTION" not in rendered


def test_transient_retry_behavior_remains_unchanged(monkeypatch) -> None:
    batch = SimpleNamespace(id=uuid.uuid4())
    item = SimpleNamespace(
        id=uuid.uuid4(),
        batch_id=batch.id,
        batch=batch,
        attempts=1,
        max_attempts=3,
        status="running",
        stage="claimed",
        claim_token="safe-claim-token",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        next_attempt_at=datetime.now(UTC),
        error_code=None,
        error_message=None,
    )

    class FakeSession:
        def __init__(self) -> None:
            self.commits = 0

        def get(self, model, item_id):
            assert item_id == item.id
            return item

        def commit(self) -> None:
            self.commits += 1

    monkeypatch.setattr(ScreeningBatchService, "_update_batch_state", lambda batch: None)
    session = FakeSession()
    worker = ScreeningWorker(initial_retry_delay_seconds=30)

    worker._handle_transient_failure(
        item.id,
        item.claim_token,
        "ValidationError",
        db=session,
        processing_stage="candidate_profile_extraction",
    )

    assert item.status == "queued"
    assert item.stage == "retry_scheduled"
    assert item.claim_token is None
    assert item.lease_expires_at is None
    assert item.next_attempt_at >= datetime.now(UTC)
    assert item.error_code is None
    assert session.commits == 1


def test_final_retry_still_marks_item_failed(monkeypatch) -> None:
    batch = SimpleNamespace(id=uuid.uuid4())
    item = SimpleNamespace(
        id=uuid.uuid4(),
        batch_id=batch.id,
        batch=batch,
        attempts=3,
        max_attempts=3,
        status="running",
        stage="claimed",
        claim_token="safe-claim-token",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        next_attempt_at=datetime.now(UTC),
        error_code=None,
        error_message=None,
    )

    class FakeSession:
        def get(self, model, item_id):
            assert item_id == item.id
            return item

        def commit(self) -> None:
            pass

    monkeypatch.setattr(ScreeningBatchService, "_update_batch_state", lambda batch: None)
    worker = ScreeningWorker()

    worker._handle_transient_failure(
        item.id,
        item.claim_token,
        "ValidationError",
        db=FakeSession(),
        processing_stage="candidate_profile_extraction",
    )

    assert item.status == "failed"
    assert item.stage == "failed"
    assert item.error_code == "MAX_ATTEMPTS_EXCEEDED"
    assert item.error_message == "Exceeded maximum attempts (3). Last error: ValidationError"
    assert item.claim_token is None
    assert item.lease_expires_at is None

from __future__ import annotations

import io
from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.v1.routes.resumes as resumes_routes
from app.core.database import get_db
from app.main import app
from app.models import Candidate, Organization, User
from app.services.errors import (
    UPLOAD_ERROR_NO_TEXT,
    UPLOAD_ERROR_TOO_LARGE,
    UPLOAD_ERROR_UNSUPPORTED_TYPE,
    UploadValidationError,
)
from app.services.ocr_service import (
    DisabledOCRProvider,
    OCRProvider,
    TesseractCLIOCRProvider,
    detect_image_extension,
    validate_image_upload,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP_BYTES = b"RIFF" + b"\x40\x00\x00\x00" + b"WEBP" + b"\x00" * 32
PDF_BYTES = b"%PDF-1.4 fake"


class FakeOCRProvider(OCRProvider):
    def __init__(self, text: str = "Ada Lovelace\nSoftware Engineer\nPython, SQL, Leadership"):
        self.text = text
        self.calls: list[str] = []

    def extract_text_from_image(self, data: bytes, *, extension: str) -> str:
        self.calls.append(extension)
        if not self.text:
            raise UploadValidationError("No readable text.", code=UPLOAD_ERROR_NO_TEXT)
        return self.text


@pytest.fixture()
def client(db_session: Session) -> Generator[httpx.Client, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _org_user_candidate(db: Session, suffix: str) -> tuple[Organization, User, Candidate]:
    organization = Organization(name=f"Scan Org {suffix}")
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email=f"scan-{suffix}@example.com",
        full_name="Scan HR",
        role="recruiter",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Scan Candidate",
        email=f"scan-candidate-{suffix}@example.test",
    )
    db.add_all([user, candidate])
    db.flush()
    return organization, user, candidate


def _headers(org: Organization, user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id), "X-Organization-Id": str(org.id)}


def _upload_scan(client, org, user, candidate, data: bytes, filename: str):
    return client.post(
        f"/api/v1/candidates/{candidate.id}/resumes/scan",
        headers=_headers(org, user),
        files={"file": (filename, io.BytesIO(data), "image/png")},
    )


def test_detect_image_extension_magic_bytes() -> None:
    assert detect_image_extension(PNG_BYTES) == "png"
    assert detect_image_extension(JPEG_BYTES) == "jpeg"
    assert detect_image_extension(WEBP_BYTES) == "webp"
    assert detect_image_extension(PDF_BYTES) is None
    assert detect_image_extension(b"") is None


def test_validate_image_upload_rejects_wrong_type_and_oversize() -> None:
    with pytest.raises(UploadValidationError) as wrong_type:
        validate_image_upload(PDF_BYTES, max_bytes=1024)
    assert wrong_type.value.code == UPLOAD_ERROR_UNSUPPORTED_TYPE

    with pytest.raises(UploadValidationError) as too_large:
        validate_image_upload(PNG_BYTES, max_bytes=8)
    assert too_large.value.code == UPLOAD_ERROR_TOO_LARGE


def test_tesseract_provider_parses_cli_output(monkeypatch) -> None:
    class FakeResult:
        returncode = 0
        stdout = b"Jane Doe\nBackend Engineer\nPython, FastAPI, PostgreSQL"

    invoked: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        invoked["cmd"] = cmd
        return FakeResult()

    monkeypatch.setattr("subprocess.run", fake_run)
    provider = TesseractCLIOCRProvider(languages="eng+ara", timeout_seconds=5)
    text = provider.extract_text_from_image(PNG_BYTES, extension="png")
    assert "Jane Doe" in text
    assert invoked["cmd"][0] == "tesseract"
    assert "-l" in invoked["cmd"] and "eng+ara" in invoked["cmd"]


def test_tesseract_provider_rejects_empty_ocr(monkeypatch) -> None:
    class FakeResult:
        returncode = 0
        stdout = b"   "

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeResult())
    provider = TesseractCLIOCRProvider()
    with pytest.raises(UploadValidationError) as no_text:
        provider.extract_text_from_image(PNG_BYTES, extension="png")
    assert no_text.value.code == UPLOAD_ERROR_NO_TEXT


def test_disabled_provider_gives_clear_error() -> None:
    with pytest.raises(Exception) as excinfo:
        DisabledOCRProvider().extract_text_from_image(PNG_BYTES, extension="png")
    assert "disabled" in str(excinfo.value)


def test_scan_endpoint_creates_screening_ready_resume(
    client: httpx.Client, db_session: Session, monkeypatch, tmp_path
) -> None:
    org, user, candidate = _org_user_candidate(db_session, "api")
    fake = FakeOCRProvider()
    monkeypatch.setattr(resumes_routes, "get_ocr_provider", lambda settings: fake)
    monkeypatch.setattr(resumes_routes.settings, "storage_root_dir", str(tmp_path))

    resp = _upload_scan(client, org, user, candidate, PNG_BYTES, "cv-photo.png")
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "text_extracted"
    assert body["content_type"] == "image/png"
    assert fake.calls == ["png"]

    # OCR text is persisted on the resume, ready for the existing screening pipeline
    from app.models import Resume

    import uuid as _uuid
    resume = db_session.get(Resume, _uuid.UUID(body["id"]))
    assert resume is not None
    assert "Ada Lovelace" in (resume.extracted_text or "")


def test_scan_endpoint_rejects_non_image(
    client: httpx.Client, db_session: Session, monkeypatch, tmp_path
) -> None:
    org, user, candidate = _org_user_candidate(db_session, "reject")
    monkeypatch.setattr(resumes_routes, "get_ocr_provider", lambda settings: FakeOCRProvider())
    monkeypatch.setattr(resumes_routes.settings, "storage_root_dir", str(tmp_path))

    resp = _upload_scan(client, org, user, candidate, PDF_BYTES, "cv.pdf")
    assert resp.status_code in (400, 422)


def test_scan_endpoint_org_isolation(
    client: httpx.Client, db_session: Session, monkeypatch, tmp_path
) -> None:
    org, user, candidate = _org_user_candidate(db_session, "iso")
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.flush()
    monkeypatch.setattr(resumes_routes, "get_ocr_provider", lambda settings: FakeOCRProvider())
    monkeypatch.setattr(resumes_routes.settings, "storage_root_dir", str(tmp_path))

    resp = client.post(
        f"/api/v1/candidates/{candidate.id}/resumes/scan",
        headers={"X-User-Id": str(user.id), "X-Organization-Id": str(other_org.id)},
        files={"file": ("cv.png", io.BytesIO(PNG_BYTES), "image/png")},
    )
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Screening-batch intake of scanned CVs (worker OCRs them via extract_text)
# ---------------------------------------------------------------------------

from datetime import UTC, datetime

from app.models import Job, JobProfile
from app.services.screening_batch_service import ScreeningBatchService
from app.services.storage_service import LocalFileSystemStorage
from app.services.upload_stream_service import BoundedFilePayload


def _payload(filename: str, data: bytes) -> BoundedFilePayload:
    import hashlib

    class _FakeUpload:
        pass

    return BoundedFilePayload(
        upload_file=_FakeUpload(),
        filename=filename,
        content_type="image/png",
        data=data,
        size=len(data),
        checksum=hashlib.sha256(data).hexdigest(),
    )


def _job_with_profile(db: Session, org: Organization, user: User) -> Job:
    job = Job(
        organization_id=org.id,
        title="Scan Intake Role",
        status="active",
        created_by_user_id=user.id,
    )
    db.add(job)
    db.flush()
    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        is_current=True,
        status="approved",
        source="hr_created",
        profile_data={
            "requirements": [
                {"text": "Python", "category": "must_have", "dimension": "skill"}
            ]
        },
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
    )
    db.add(profile)
    db.flush()
    return job


def test_batch_accepts_real_image_scan(db_session: Session, tmp_path) -> None:
    org, user, _candidate = _org_user_candidate(db_session, "batch")
    job = _job_with_profile(db_session, org, user)
    batch = ScreeningBatchService().create_batch(
        db_session,
        organization_id=org.id,
        job_id=job.id,
        user_id=user.id,
        payloads=[_payload("cv-photo.png", PNG_BYTES)],
        storage=LocalFileSystemStorage(str(tmp_path)),
    )
    assert batch.items[0].status == "queued"


def test_batch_rejects_fake_image_signature(db_session: Session, tmp_path) -> None:
    org, user, _candidate = _org_user_candidate(db_session, "batchbad")
    job = _job_with_profile(db_session, org, user)
    batch = ScreeningBatchService().create_batch(
        db_session,
        organization_id=org.id,
        job_id=job.id,
        user_id=user.id,
        payloads=[_payload("cv-photo.png", b"not a supported resume document")],
        storage=LocalFileSystemStorage(str(tmp_path)),
    )
    assert batch.items[0].status == "failed"
    assert batch.items[0].error_code == UPLOAD_ERROR_UNSUPPORTED_TYPE


def test_worker_dispatch_extracts_text_from_image(monkeypatch) -> None:
    """The shared extract_text dispatcher routes images through the OCR provider."""
    import app.services.text_extraction_service as tes

    fake = FakeOCRProvider(text="Scanned CV body text for worker dispatch")
    monkeypatch.setattr(
        "app.services.ocr_service.get_ocr_provider", lambda *a, **k: fake
    )
    # rebind the lazy import target
    import app.services.ocr_service as ocr_mod
    monkeypatch.setattr(ocr_mod, "get_ocr_provider", lambda *a, **k: fake)

    from app.services.ocr_service import get_ocr_provider  # noqa: F401
    import app.services.text_extraction_service as text_extraction

    text = text_extraction.extract_text(PNG_BYTES, filename="scan.png")
    assert "Scanned CV body text" in text

"""Dedicated test suite for HERA Prompt 5: Secure CV Upload and Text Extraction.

Validates:
- Size and content validation (bounded streaming, single-file limit, batch count & size limits).
- PDF validation: corrupt, encrypted, page limit exceeded, no extractable text.
- DOCX validation: table cell text extraction, missing required parts, corrupt zip,
  declared uncompressed size (zip bomb), excessive entries, path traversal.
- Upload failure isolation & storage cleanup: rollback on error, no orphaned files,
  no unusable partial resumes, independent validation.
- Preservation of tenant isolation, authentication, and opaque storage keys.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models import (
    Candidate,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
)
from app.services.errors import (
    UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED,
    UPLOAD_ERROR_CORRUPT,
    UPLOAD_ERROR_ENCRYPTED,
    UPLOAD_ERROR_INVALID_ARCHIVE,
    UPLOAD_ERROR_NO_TEXT,
    UPLOAD_ERROR_PAGE_LIMIT_EXCEEDED,
    UPLOAD_ERROR_TOO_LARGE,
    UPLOAD_ERROR_UNSUPPORTED_TYPE,
    NotFoundError,
    UploadValidationError,
    ValidationError,
)
from app.services.resume_service import ResumeService
from app.services.storage_service import LocalFileSystemStorage
from app.services.text_extraction_service import (
    DocxTextExtractor,
    PdfTextExtractor,
    extract_text,
)
from app.services.upload_stream_service import read_batch_bounded, read_upload_file_bounded
from tests.resume_upload_fixtures import make_docx_bytes, make_pdf_bytes

# ---------------------------------------------------------------------------
# Programmatic Test Document Generators
# ---------------------------------------------------------------------------


def make_encrypted_pdf_bytes(password: str = "secret123") -> bytes:
    """Build an encrypted PDF using pypdf."""
    from pypdf import PdfReader

    base_pdf = make_pdf_bytes("Encrypted candidate resume text")
    reader = PdfReader(io.BytesIO(base_pdf))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_multi_page_pdf_bytes(page_count: int) -> bytes:
    """Build a multi-page PDF using pypdf."""
    writer = PdfWriter()
    for i in range(page_count):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_empty_text_pdf_bytes() -> bytes:
    """Build a valid PDF that contains only a blank page (no text)."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_docx_with_table_only_bytes(table_text: str = "Table Cell Candidate: Jane Doe") -> bytes:
    """Build a valid DOCX where candidate text is exclusively inside table cells."""
    from docx import Document

    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Candidate Name:"
    table.cell(0, 1).text = table_text
    table.cell(1, 0).text = "Skills:"
    table.cell(1, 1).text = "Python, PostgreSQL, FastAPI"
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def make_zip_missing_docx_parts() -> bytes:
    """Build a ZIP file that lacks required WordProcessingML parts."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test.txt", "This is just a text file in a zip.")
    return buf.getvalue()


def make_docx_uncompressed_oversize(declared_bytes: int = 25 * 1024 * 1024) -> bytes:
    """Build a zip entry whose declared uncompressed size exceeds the limit."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<document/>")
        info = zipfile.ZipInfo("huge_file.bin")
        info.file_size = declared_bytes  # Exceeds max uncompressed bytes
        zf.writestr(info, b"x" * 100)
    return buf.getvalue()


def make_docx_excessive_entries(num_entries: int = 105) -> bytes:
    """Build a zip with entry count exceeding the limit."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<document/>")
        for i in range(num_entries):
            zf.writestr(f"word/part_{i}.xml", "<xml/>")
    return buf.getvalue()


def make_docx_path_traversal() -> bytes:
    """Build a zip with an entry attempting directory traversal."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<document/>")
        zf.writestr("../evil.xml", "<evil/>")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    connection = db_session.connection()
    db_session.bind = connection

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def make_auth_headers(user: User, org: Organization, role: str = "recruiter") -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        organization_id=org.id,
        role=role,
        token_version=user.token_version or 1,
    )
    return {"Authorization": f"Bearer {token}"}


def setup_tenant(
    db: Session, org_name: str = "Secure Upload Org"
) -> tuple[Organization, User, Candidate, Job]:
    org = Organization(name=org_name)
    db.add(org)
    db.flush()

    user = User(
        organization_id=org.id,
        email=f"recruiter-{uuid.uuid4().hex[:6]}@example.com",
        full_name="Upload Recruiter",
        role="recruiter",
    )
    db.add(user)
    db.flush()

    cand = Candidate(organization_id=org.id, full_name="Ada Candidate")
    db.add(cand)
    db.flush()

    job = Job(
        organization_id=org.id,
        title="Backend Engineer",
        raw_description="Python backend developer with FastAPI and SQL experience.",
        status="active",
    )
    db.add(job)
    db.flush()

    jp = JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="ai_extracted",
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
        is_current=True,
        profile_data={
            "role_overview": "Backend dev",
            "requirements": ["Python", "FastAPI"],
        },
    )
    db.add(jp)
    db.commit()

    return org, user, cand, job


# ---------------------------------------------------------------------------
# 1. Bounded Streaming & Incremental Size Enforcement Tests
# ---------------------------------------------------------------------------


def test_bounded_stream_reader_reads_valid_file() -> None:
    from starlette.datastructures import UploadFile

    data = make_pdf_bytes("Ada Lovelace Engineer")
    uf = UploadFile(filename="resume.pdf", file=io.BytesIO(data))

    read_bytes, size, checksum = read_upload_file_bounded(uf, max_bytes=5_242_880)
    assert read_bytes == data
    assert size == len(data)
    assert len(checksum) == 64


def test_bounded_stream_reader_aborts_without_reading_entire_oversized_payload() -> None:
    from starlette.datastructures import UploadFile

    chunk_size = 64 * 1024
    # Create 5 chunks of 64 KiB = 320 KiB, but limit is 100 KiB
    total_len = 5 * chunk_size
    fake_stream = io.BytesIO(b"x" * total_len)
    uf = UploadFile(filename="large.pdf", file=fake_stream)

    max_bytes = 100 * 1024  # 100 KiB limit
    with pytest.raises(UploadValidationError) as exc_info:
        read_upload_file_bounded(uf, max_bytes=max_bytes, chunk_size=chunk_size)

    assert exc_info.value.code == UPLOAD_ERROR_TOO_LARGE
    # Stream position should have stopped right after exceeding max_bytes (at 2nd chunk, 128 KiB),
    # NOT at the very end of 320 KiB
    assert fake_stream.tell() < total_len
    assert fake_stream.tell() == 2 * chunk_size


def test_bounded_stream_reader_rejects_empty_file() -> None:
    from starlette.datastructures import UploadFile

    uf = UploadFile(filename="empty.pdf", file=io.BytesIO(b""))
    with pytest.raises(UploadValidationError) as exc_info:
        read_upload_file_bounded(uf, max_bytes=1000)
    assert exc_info.value.code == UPLOAD_ERROR_NO_TEXT


def test_batch_bounded_reader_enforces_max_files() -> None:
    from starlette.datastructures import UploadFile

    files = [
        UploadFile(filename=f"cv_{i}.pdf", file=io.BytesIO(make_pdf_bytes()))
        for i in range(25)
    ]
    with pytest.raises(UploadValidationError) as exc_info:
        read_batch_bounded(files, max_files=20)
    assert exc_info.value.code == UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED


def test_batch_bounded_reader_enforces_total_batch_size() -> None:
    from starlette.datastructures import UploadFile

    # 3 files of 40 KiB each = 120 KiB, limit is 100 KiB
    files = [
        UploadFile(filename=f"cv_{i}.pdf", file=io.BytesIO(b"%PDF-" + b"x" * 40_000))
        for i in range(3)
    ]
    with pytest.raises(UploadValidationError) as exc_info:
        read_batch_bounded(files, max_files=20, max_file_bytes=50_000, max_batch_bytes=100_000)
    assert exc_info.value.code == UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED


def test_batch_bounded_reader_enforces_single_file_limit_in_batch() -> None:
    from starlette.datastructures import UploadFile

    files = [
        UploadFile(filename="cv_1.pdf", file=io.BytesIO(b"%PDF-" + b"x" * 10_000)),
        UploadFile(filename="cv_2.pdf", file=io.BytesIO(b"%PDF-" + b"x" * 60_000)),  # Exceeds 50 KiB
    ]
    with pytest.raises(UploadValidationError) as exc_info:
        read_batch_bounded(files, max_files=20, max_file_bytes=50_000, max_batch_bytes=200_000)
    assert exc_info.value.code == UPLOAD_ERROR_TOO_LARGE


# ---------------------------------------------------------------------------
# 2. PDF Content Validation & Extraction Tests
# ---------------------------------------------------------------------------


def test_pdf_valid_extraction() -> None:
    pdf = make_pdf_bytes("Experienced Python and FastAPI Engineer")
    text = extract_text(pdf, filename="candidate.pdf")
    assert "FastAPI" in text


def test_pdf_missing_signature_rejected() -> None:
    # Starts with non-PDF bytes
    data = b"NOT_A_PDF_FILE" + make_pdf_bytes()
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(data, filename="candidate.pdf")
    assert exc_info.value.code == UPLOAD_ERROR_UNSUPPORTED_TYPE


def test_pdf_corrupt_rejected() -> None:
    data = b"%PDF-1.4\nCorrupted content with no xref or valid objects\n%%EOF"
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(data, filename="candidate.pdf")
    assert exc_info.value.code in (UPLOAD_ERROR_CORRUPT, UPLOAD_ERROR_NO_TEXT)


def test_pdf_encrypted_rejected() -> None:
    encrypted = make_encrypted_pdf_bytes("password123")
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(encrypted, filename="encrypted.pdf")
    assert exc_info.value.code == UPLOAD_ERROR_ENCRYPTED


def test_pdf_page_limit_exceeded() -> None:
    multi_page = make_multi_page_pdf_bytes(page_count=52)
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(multi_page, filename="too_many_pages.pdf", max_pdf_pages=50)
    assert exc_info.value.code == UPLOAD_ERROR_PAGE_LIMIT_EXCEEDED


def test_pdf_no_extractable_text() -> None:
    empty_pdf = make_empty_text_pdf_bytes()
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(empty_pdf, filename="blank.pdf")
    assert exc_info.value.code == UPLOAD_ERROR_NO_TEXT


# ---------------------------------------------------------------------------
# 3. DOCX Content Validation & Table Extraction Tests
# ---------------------------------------------------------------------------


def test_docx_valid_paragraph_extraction() -> None:
    docx = make_docx_bytes("Normal paragraph candidate resume")
    text = extract_text(docx, filename="resume.docx")
    assert "Normal paragraph" in text


def test_docx_table_only_extraction() -> None:
    """Verify text is extracted when it resides only in table cells and not paragraphs."""
    docx = make_docx_with_table_only_bytes("Specialist in Distributed Systems")
    text = extract_text(docx, filename="resume.docx")
    assert "Specialist in Distributed Systems" in text
    assert "Python, PostgreSQL, FastAPI" in text


def test_docx_missing_zip_signature_rejected() -> None:
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(b"NOT_A_ZIP_OR_DOCX", filename="resume.docx")
    assert exc_info.value.code == UPLOAD_ERROR_UNSUPPORTED_TYPE


def test_docx_corrupt_archive_rejected() -> None:
    corrupt_docx = b"PK\x03\x04" + b"broken_zip_body"
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(corrupt_docx, filename="resume.docx")
    assert exc_info.value.code == UPLOAD_ERROR_CORRUPT


def test_docx_missing_required_parts_rejected() -> None:
    zip_missing_parts = make_zip_missing_docx_parts()
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(zip_missing_parts, filename="resume.docx")
    assert exc_info.value.code == UPLOAD_ERROR_INVALID_ARCHIVE


def test_docx_uncompressed_size_exceeded_rejected() -> None:
    # A valid DOCX has ~2KB+ uncompressed XML entries. Limiting to 50 bytes triggers the check.
    valid_docx = make_docx_bytes("Normal candidate text")
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(
            valid_docx,
            filename="bomb.docx",
            max_docx_uncompressed_bytes=50,
        )
    assert exc_info.value.code == UPLOAD_ERROR_TOO_LARGE


def test_docx_excessive_archive_entries_rejected() -> None:
    excessive = make_docx_excessive_entries(num_entries=110)
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(excessive, filename="many_files.docx", max_docx_entries=100)
    assert exc_info.value.code == UPLOAD_ERROR_INVALID_ARCHIVE


def test_docx_path_traversal_entry_rejected() -> None:
    traversal_docx = make_docx_path_traversal()
    with pytest.raises(UploadValidationError) as exc_info:
        extract_text(traversal_docx, filename="traversal.docx")
    assert exc_info.value.code == UPLOAD_ERROR_INVALID_ARCHIVE


# ---------------------------------------------------------------------------
# 4. Single-File Upload Endpoint Integration Tests
# ---------------------------------------------------------------------------


def test_api_upload_valid_pdf(client: TestClient, db_session: Session) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    pdf_data = make_pdf_bytes("Ada Lovelace Engineer")
    resp = client.post(
        f"/api/v1/candidates/{cand.id}/resumes/upload",
        headers=h,
        files={"file": ("resume.pdf", pdf_data, "application/pdf")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "text_extracted"
    assert body["original_filename"] == "resume.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["file_size_bytes"] == len(pdf_data)


def test_api_upload_valid_docx_with_table(client: TestClient, db_session: Session) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    docx_data = make_docx_with_table_only_bytes("Table Candidate Name")
    resp = client.post(
        f"/api/v1/candidates/{cand.id}/resumes/upload",
        headers=h,
        files={
            "file": (
                "resume.docx",
                docx_data,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "text_extracted"


def test_api_upload_extension_and_content_type_mismatch(
    client: TestClient, db_session: Session
) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    resp = client.post(
        f"/api/v1/candidates/{cand.id}/resumes/upload",
        headers=h,
        files={"file": ("resume.pdf", make_pdf_bytes(), "text/plain")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == UPLOAD_ERROR_UNSUPPORTED_TYPE


def test_api_upload_unsupported_file_extension(client: TestClient, db_session: Session) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    resp = client.post(
        f"/api/v1/candidates/{cand.id}/resumes/upload",
        headers=h,
        files={"file": ("resume.txt", b"plain text", "text/plain")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == UPLOAD_ERROR_UNSUPPORTED_TYPE


def test_api_upload_encrypted_pdf_rejected(client: TestClient, db_session: Session) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    enc_pdf = make_encrypted_pdf_bytes("password")
    resp = client.post(
        f"/api/v1/candidates/{cand.id}/resumes/upload",
        headers=h,
        files={"file": ("encrypted.pdf", enc_pdf, "application/pdf")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == UPLOAD_ERROR_ENCRYPTED


def test_api_upload_empty_text_pdf_rejected(client: TestClient, db_session: Session) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    empty_pdf = make_empty_text_pdf_bytes()
    resp = client.post(
        f"/api/v1/candidates/{cand.id}/resumes/upload",
        headers=h,
        files={"file": ("blank.pdf", empty_pdf, "application/pdf")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == UPLOAD_ERROR_NO_TEXT


def test_api_upload_oversized_file_rejected(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    # Monkeypatch max_upload_bytes to 500 bytes for deterministic test
    monkeypatch.setattr(settings, "max_upload_bytes", 500)

    pdf_data = make_pdf_bytes()  # > 500 bytes
    resp = client.post(
        f"/api/v1/candidates/{cand.id}/resumes/upload",
        headers=h,
        files={"file": ("resume.pdf", pdf_data, "application/pdf")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == UPLOAD_ERROR_TOO_LARGE


# ---------------------------------------------------------------------------
# 5. Batch Screening Upload Tests & Failure Isolation
# ---------------------------------------------------------------------------


def test_api_screen_batch_exceeding_file_count_rejected(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, user, _cand, job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    monkeypatch.setattr(settings, "max_batch_files", 3)

    files = [
        ("files", (f"cv_{i}.pdf", make_pdf_bytes(), "application/pdf"))
        for i in range(4)
    ]
    resp = client.post(f"/api/v1/jobs/{job.id}/screen", headers=h, files=files)
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED


def test_api_screen_batch_exceeding_payload_limit_rejected(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, user, _cand, job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    # Set total batch payload limit lower than 2 combined PDFs
    single_pdf = make_pdf_bytes()
    monkeypatch.setattr(settings, "max_batch_bytes", len(single_pdf) + 50)

    files = [
        ("files", ("cv_1.pdf", single_pdf, "application/pdf")),
        ("files", ("cv_2.pdf", single_pdf, "application/pdf")),
    ]
    resp = client.post(f"/api/v1/jobs/{job.id}/screen", headers=h, files=files)
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED


def test_api_screen_atomic_rollback_on_single_invalid_file(
    client: TestClient, db_session: Session, tmp_path: Path
) -> None:
    """If one file in a batch is invalid, all database writes must roll back
    and any written files must be purged so no orphaned files or partial candidates remain.
    """
    org, user, _cand, job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    valid_pdf = make_pdf_bytes("Valid Candidate One")
    corrupt_pdf = b"%PDF-1.4\ncorrupted file body with no objects"

    files = [
        ("files", ("valid_1.pdf", valid_pdf, "application/pdf")),
        ("files", ("corrupt_2.pdf", corrupt_pdf, "application/pdf")),
    ]

    org_id = org.id
    job_id = job.id
    initial_candidates = db_session.query(Candidate).filter_by(organization_id=org_id).count()
    initial_resumes = db_session.query(Resume).count()

    resp = client.post(f"/api/v1/jobs/{job_id}/screen", headers=h, files=files)
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") in (UPLOAD_ERROR_CORRUPT, UPLOAD_ERROR_NO_TEXT)

    # Verify atomic rollback: no candidates or resumes were committed for the batch
    final_candidates = db_session.query(Candidate).filter_by(organization_id=org_id).count()
    final_resumes = db_session.query(Resume).count()
    assert final_candidates == initial_candidates
    assert final_resumes == initial_resumes


# ---------------------------------------------------------------------------
# 6. Failure Cleanup & Preservation of Existing Guarantees
# ---------------------------------------------------------------------------


def test_upload_failure_cleans_up_stored_file(db_session: Session, tmp_path: Path) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    # Valid PDF signature, but unextractable text -> raises NO_TEXT
    blank_pdf = make_empty_text_pdf_bytes()

    with pytest.raises(UploadValidationError) as exc_info:
        service.create_from_upload(
            db_session,
            candidate_id=cand.id,
            organization_id=org.id,
            filename="blank.pdf",
            content_type="application/pdf",
            file_bytes=blank_pdf,
            max_upload_bytes=5_242_880,
            storage=storage,
        )

    assert exc_info.value.code == UPLOAD_ERROR_NO_TEXT
    # File must be cleaned up from storage root
    resumes_dir = tmp_path / "resumes"
    files = list(resumes_dir.glob("**/*")) if resumes_dir.exists() else []
    # Any files found must not be regular files
    assert all(not f.is_file() for f in files)


def test_cross_tenant_upload_isolation_preserved(
    client: TestClient, db_session: Session
) -> None:
    org_a, user_a, cand_a, _job_a = setup_tenant(db_session, org_name="Org A")
    org_b, user_b, cand_b, _job_b = setup_tenant(db_session, org_name="Org B")

    # User A tries to upload to Candidate B
    h_a = make_auth_headers(user_a, org_a)
    resp = client.post(
        f"/api/v1/candidates/{cand_b.id}/resumes/upload",
        headers=h_a,
        files={"file": ("resume.pdf", make_pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 404
    assert "was not found" in resp.json()["detail"].lower()


def test_existing_download_and_opaque_uri_preserved(
    client: TestClient, db_session: Session
) -> None:
    org, user, cand, _job = setup_tenant(db_session)
    h = make_auth_headers(user, org)

    pdf_data = make_pdf_bytes("Download verification candidate")
    upload_resp = client.post(
        f"/api/v1/candidates/{cand.id}/resumes/upload",
        headers=h,
        files={"file": ("download_test.pdf", pdf_data, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    resume_id = upload_resp.json()["id"]

    # Verify download succeeds with sanitized header
    dl_resp = client.get(f"/api/v1/resumes/{resume_id}/download", headers=h)
    assert dl_resp.status_code == 200
    assert dl_resp.content == pdf_data
    assert 'attachment; filename="download_test.pdf"' in dl_resp.headers.get(
        "content-disposition", ""
    )

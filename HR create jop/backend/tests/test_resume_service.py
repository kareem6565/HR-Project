"""Tests for the Phase 4.4 resume upload and extraction service methods."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models import Candidate, Organization
from app.services.errors import (
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from app.services.resume_service import ResumeService
from app.services.storage_service import LocalFileSystemStorage
from tests.resume_upload_fixtures import (
    DOCX_TEXT,
    PDF_TEXT,
    make_docx_bytes,
    make_pdf_bytes,
)


def _org_and_candidate(
    db_session: Session, name: str = "Upload Org"
) -> tuple[Organization, Candidate]:
    org = Organization(name=name)
    db_session.add(org)
    db_session.flush()
    candidate = Candidate(organization_id=org.id, full_name="Upload Candidate")
    db_session.add(candidate)
    db_session.flush()
    return org, candidate


def test_upload_pdf_stores_file_and_text(db_session: Session, tmp_path: Path) -> None:
    org, candidate = _org_and_candidate(db_session)
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    resume = service.create_from_upload(
        db_session,
        candidate_id=candidate.id,
        organization_id=org.id,
        filename="resume.pdf",
        content_type="application/pdf",
        file_bytes=make_pdf_bytes(),
        max_upload_bytes=5_000_000,
        storage=storage,
    )
    db_session.commit()

    assert resume.status == "text_extracted"
    assert resume.extracted_text is not None
    assert PDF_TEXT in resume.extracted_text
    assert resume.original_filename == "resume.pdf"
    assert resume.content_type == "application/pdf"
    assert resume.checksum is not None

    # File exists under storage root, and file_uri is an opaque relative key
    assert not Path(resume.file_uri).is_absolute()
    path = storage._root_dir / resume.file_uri
    assert path.exists()
    assert storage.read(file_uri=resume.file_uri) == make_pdf_bytes()


def test_upload_docx_stores_file_and_text(db_session: Session, tmp_path: Path) -> None:
    org, candidate = _org_and_candidate(db_session)
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    resume = service.create_from_upload(
        db_session,
        candidate_id=candidate.id,
        organization_id=org.id,
        filename="resume.docx",
        content_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        file_bytes=make_docx_bytes(),
        max_upload_bytes=5_000_000,
        storage=storage,
    )
    db_session.commit()

    assert resume.status == "text_extracted"
    assert DOCX_TEXT in resume.extracted_text
    assert not Path(resume.file_uri).is_absolute()
    assert (storage._root_dir / resume.file_uri).exists()


def test_upload_oversize_raises_and_no_file_written(db_session: Session, tmp_path: Path) -> None:
    org, candidate = _org_and_candidate(db_session)
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()
    oversized = b"x" * 100

    with pytest.raises(ValidationError) as exc_info:
        service.create_from_upload(
            db_session,
            candidate_id=candidate.id,
            organization_id=org.id,
            filename="resume.pdf",
            content_type="application/pdf",
            file_bytes=oversized,
            max_upload_bytes=10,
            storage=storage,
        )
    assert "maximum size" in str(exc_info.value)
    resume_dirs = tmp_path / "resumes"
    files = list(resume_dirs.glob("**/*")) if resume_dirs.exists() else []
    assert files == []


def test_upload_extension_content_type_mismatch(db_session: Session, tmp_path: Path) -> None:
    org, candidate = _org_and_candidate(db_session)
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    with pytest.raises(ValidationError):
        service.create_from_upload(
            db_session,
            candidate_id=candidate.id,
            organization_id=org.id,
            filename="resume.pdf",
            content_type="application/x-unknown",
            file_bytes=make_pdf_bytes(),
            max_upload_bytes=5_000_000,
            storage=storage,
        )


def test_upload_unsupported_extension(db_session: Session, tmp_path: Path) -> None:
    org, candidate = _org_and_candidate(db_session)
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    with pytest.raises(ValidationError):
        service.create_from_upload(
            db_session,
            candidate_id=candidate.id,
            organization_id=org.id,
            filename="resume.txt",
            content_type="text/plain",
            file_bytes=b"hello",
            max_upload_bytes=5_000_000,
            storage=storage,
        )


def test_upload_unextractable_text_raises_and_removes_file(
    db_session: Session, tmp_path: Path
) -> None:
    org, candidate = _org_and_candidate(db_session)
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    # Valid .pdf extension/type but a body pypdf can't extract -> no text.
    fake_pdf = b"%PDF-1.4\nnot a real pdf file"

    with pytest.raises(ValidationError):
        service.create_from_upload(
            db_session,
            candidate_id=candidate.id,
            organization_id=org.id,
            filename="resume.pdf",
            content_type="application/pdf",
            file_bytes=fake_pdf,
            max_upload_bytes=5_000_000,
            storage=storage,
        )

    # No orphaned file should remain under the storage root.
    resume_dirs = tmp_path / "resumes"
    files = list(resume_dirs.glob("**/*")) if resume_dirs.exists() else []
    assert files == []


def test_upload_cross_org_isolated(db_session: Session, tmp_path: Path) -> None:
    org1, _ = _org_and_candidate(db_session, name="Org1")
    _, candidate2 = _org_and_candidate(db_session, name="Org2")
    storage1 = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    with pytest.raises(NotFoundError):
        service.create_from_upload(
            db_session,
            candidate_id=candidate2.id,
            organization_id=org1.id,
            filename="resume.pdf",
            content_type="application/pdf",
            file_bytes=make_pdf_bytes(),
            max_upload_bytes=5_000_000,
            storage=storage1,
        )


def test_upload_nonexistent_candidate(db_session: Session, tmp_path: Path) -> None:
    org, _ = _org_and_candidate(db_session)
    import uuid

    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    with pytest.raises(NotFoundError):
        service.create_from_upload(
            db_session,
            candidate_id=uuid.uuid4(),
            organization_id=org.id,
            filename="resume.pdf",
            content_type="application/pdf",
            file_bytes=make_pdf_bytes(),
            max_upload_bytes=5_000_000,
            storage=storage,
        )


def test_get_extracted_text_ok(db_session: Session, tmp_path: Path) -> None:
    org, candidate = _org_and_candidate(db_session)
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    resume = service.create_from_upload(
        db_session,
        candidate_id=candidate.id,
        organization_id=org.id,
        filename="resume.pdf",
        content_type="application/pdf",
        file_bytes=make_pdf_bytes(),
        max_upload_bytes=5_000_000,
        storage=storage,
    )
    db_session.commit()

    text = service.get_extracted_text(db_session, resume_id=resume.id, organization_id=org.id)
    assert PDF_TEXT in text


def test_get_extracted_text_for_missing_resume(db_session: Session) -> None:
    org, _ = _org_and_candidate(db_session)
    import uuid

    service = ResumeService()
    with pytest.raises(NotFoundError):
        service.get_extracted_text(
            db_session,
            resume_id=uuid.uuid4(),
            organization_id=org.id,
        )


def test_get_extracted_text_cross_org(db_session: Session, tmp_path: Path) -> None:
    org1, candidate = _org_and_candidate(db_session, name="Org1")
    org2, _ = _org_and_candidate(db_session, name="Org2")
    storage = LocalFileSystemStorage(tmp_path)
    service = ResumeService()

    resume = service.create_from_upload(
        db_session,
        candidate_id=candidate.id,
        organization_id=org1.id,
        filename="resume.pdf",
        content_type="application/pdf",
        file_bytes=make_pdf_bytes(),
        max_upload_bytes=5_000_000,
        storage=storage,
    )
    db_session.commit()

    with pytest.raises(NotFoundError):
        service.get_extracted_text(db_session, resume_id=resume.id, organization_id=org2.id)


def test_get_extracted_text_no_text_available(db_session: Session) -> None:
    from app.models import Resume

    org, candidate = _org_and_candidate(db_session)
    resume = Resume(candidate_id=candidate.id, file_uri="local://r.pdf")
    db_session.add(resume)
    db_session.flush()

    service = ResumeService()
    with pytest.raises(InvalidStateError):
        service.get_extracted_text(db_session, resume_id=resume.id, organization_id=org.id)

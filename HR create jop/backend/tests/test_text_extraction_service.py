"""Tests for the Phase 4.4 text extraction service."""

from __future__ import annotations

import pytest

from app.services.errors import ValidationError
from app.services.text_extraction_service import (
    DOCX_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    extension_for_filename,
    extract_text,
)
from tests.resume_upload_fixtures import DOCX_TEXT, PDF_TEXT, make_docx_bytes, make_pdf_bytes


def test_extract_pdf_text() -> None:
    text = extract_text(make_pdf_bytes(), filename="resume.pdf")
    assert PDF_TEXT in text


def test_extract_docx_text() -> None:
    text = extract_text(make_docx_bytes(), filename="resume.docx")
    assert DOCX_TEXT in text


def test_wrong_content_type_mismatch_is_not_enforced_here() -> None:
    # extract_text works on bytes + filename only; content-type matching is
    # validated by the service layer. A .pdf with a .docx filename still raises.
    pdf = make_pdf_bytes()
    with pytest.raises(ValidationError):
        extract_text(pdf, filename="resume.docx")


@pytest.mark.parametrize(
    "filename",
    ["resume.txt", "resume.png", "resume", "resume.exe", ""],
)
def test_unsupported_extension_raises(filename: str) -> None:
    if filename:
        with pytest.raises(ValidationError):
            extract_text(b"some bytes", filename=filename)
    else:
        with pytest.raises(ValidationError):
            extract_text(b"some bytes", filename=filename)


def test_no_filename_raises() -> None:
    with pytest.raises(ValidationError):
        extract_text(b"bytes", filename="")


def test_empty_text_raises() -> None:
    # A valid PDF with no extractable text yields no text -> ValidationError.
    with pytest.raises(ValidationError):
        extract_text(b"%PDF-1.4\nnot a real pdf", filename="resume.pdf")


def test_extension_for_filename_ok() -> None:
    assert extension_for_filename("resume.PDF") == "pdf"
    assert extension_for_filename("resume.docx") == "docx"


def test_extension_for_filename_unsupported() -> None:
    with pytest.raises(ValidationError):
        extension_for_filename("resume.txt")


def test_content_type_constants() -> None:
    assert PDF_CONTENT_TYPE == "application/pdf"
    assert DOCX_CONTENT_TYPE == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

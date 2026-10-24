"""Shared test fixtures for Phase 4.4 resume upload and extraction."""

from __future__ import annotations

import io

import pytest

from app.services.text_extraction_service import (
    DOCX_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
)

PDF_TEXT = "Ada Lovelace is an engineer skilled in Python and mathematics."
DOCX_TEXT = "Alan Turing proposed the Turing test in computing."


def make_pdf_bytes(text: str = PDF_TEXT) -> bytes:
    """Build a valid single-page PDF whose text pypdf can extract."""
    content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("latin-1")
    parts = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj",
        b"4 0 obj\n<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream\nendobj",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj",
    ]
    body = b"\n".join(parts)
    xref = 42 + len(body)
    return (
        b"%PDF-1.4\n"
        + body
        + b"\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref).encode()
        + b"\n%%EOF"
    )


def make_docx_bytes(text: str = DOCX_TEXT) -> bytes:
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


@pytest.fixture()
def pdf_bytes() -> bytes:
    return make_pdf_bytes()


@pytest.fixture()
def docx_bytes() -> bytes:
    return make_docx_bytes()


@pytest.fixture()
def pdf_content_type() -> str:
    return PDF_CONTENT_TYPE


@pytest.fixture()
def docx_content_type() -> str:
    return DOCX_CONTENT_TYPE

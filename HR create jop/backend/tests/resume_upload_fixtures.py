"""Shared test fixtures for Phase 4.4 resume upload and extraction."""

from __future__ import annotations

import io
from pathlib import Path

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


def make_image_pdf(images: list[bytes | None]) -> bytes:
    """Build image-only synthetic PDF pages without a third-party PDF writer."""
    page_ids = [3 + index * 3 for index in range(len(images))]
    image_ids = [
        page_id + 2 if image is not None else None
        for page_id, image in zip(page_ids, images, strict=True)
    ]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] "
        f"/Count {len(images)} >>".encode(),
    }
    for page_id, image_id, image in zip(page_ids, image_ids, images, strict=True):
        content_id = page_id + 1
        content = b"q 520 0 0 120 40 500 cm /Im0 Do Q" if image is not None else b""
        resources = (
            f"<< /XObject << /Im0 {image_id} 0 R >> >>".encode() if image is not None else b"<< >>"
        )
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources "
            + resources
            + f" /Contents {content_id} 0 R >>".encode()
        )
        objects[content_id] = (
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )
        if image is not None:
            objects[image_id] = (
                f"<< /Type /XObject /Subtype /Image /Width 1800 /Height 420 "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(image)} >>\nstream\n".encode()
                + image
                + b"\nendstream"
            )
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, max(objects) + 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode() + objects[object_id] + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


def scanned_image(name: str) -> bytes:
    return (Path(__file__).parent / "fixtures" / name).read_bytes()


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

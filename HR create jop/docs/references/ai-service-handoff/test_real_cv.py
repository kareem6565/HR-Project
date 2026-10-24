"""
Quick manual test script — NOT part of the AI service itself.

Reads a real CV file (PDF or DOCX) from disk, extracts its raw text
(simulating what ASP.NET Core will do in production), and sends it to the
running AI service's /internal/ai/extract-cv endpoint.

Usage:
    python test_real_cv.py path\to\your\cv.pdf
    python test_real_cv.py path\to\your\cv.docx
"""
import sys
import json
import httpx

API_URL = "http://127.0.0.1:8000/internal/ai/extract-cv"


def extract_text_from_pdf(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_docx(path: str) -> str:
    import docx
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def main():
    if len(sys.argv) != 2:
        print("Usage: python test_real_cv.py <path_to_cv.pdf_or_.docx>")
        sys.exit(1)

    file_path = sys.argv[1]

    if file_path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        text = extract_text_from_docx(file_path)
    else:
        print("Only .pdf and .docx files are supported.")
        sys.exit(1)

    if not text.strip():
        print("Warning: no text could be extracted from this file (it might be a scanned image).")
        sys.exit(1)

    print(f"Extracted {len(text)} characters. Sending to AI service...\n")

    response = httpx.post(API_URL, json={"text": text}, timeout=180)

    print(f"Status: {response.status_code}\n")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Local OCR only. Versions are pinned to Debian Bookworm packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr=5.3.0-2 \
        tesseract-ocr-eng=1:4.1.0-2 \
        tesseract-ocr-ara=1:4.1.0-2 \
        tesseract-ocr-osd=1:4.1.0-2 \
        poppler-utils=22.12.0-2+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade build tools first so wheels are used
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml .
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY requirements-a5.lock .
COPY models ./models

RUN pip install --no-cache-dir . \
    && pip install --no-cache-dir --require-hashes -r requirements-a5.lock

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

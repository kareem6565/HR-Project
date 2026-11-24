FROM python:3.11-slim-bookworm AS base

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

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml .
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# Explicit opt-in image. The default target below contains neither E5 runtime nor model files.
FROM base AS backend-e5
ARG A5_E5_PACK=off
RUN test "$A5_E5_PACK" = "on" || (echo "Set A5_E5_PACK=on to build the optional E5 pack." >&2 && exit 64)
COPY requirements-a5.lock ./requirements-a5.lock
COPY models ./models
RUN pip install --no-cache-dir --no-deps --require-hashes -r requirements-a5.lock

# Last stage is the default target and intentionally remains lightweight.
FROM base AS backend
ARG A5_E5_PACK=off
RUN test "$A5_E5_PACK" = "off" || (echo "A5_E5_PACK=on requires --target backend-e5." >&2 && exit 64)
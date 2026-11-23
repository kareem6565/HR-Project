FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

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

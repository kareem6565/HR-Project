import re
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app import models  # noqa: F401
from app.core.config import settings
from app.core.database import Base


def _validated_database_name(url: URL) -> str:
    database_name = url.database
    if database_name is None or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_name):
        raise RuntimeError("TEST_DATABASE_URL must include a safe PostgreSQL database name.")
    return database_name


def _ensure_test_database_exists(test_database_url: str) -> None:
    test_url = make_url(test_database_url)
    if "sqlite" in test_url.drivername:
        return
    test_database_name = _validated_database_name(test_url)
    admin_database_name = "postgres" if test_database_name != "postgres" else "template1"
    admin_url = test_url.set(database=admin_database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)

    try:
        with admin_engine.connect() as connection:
            database_exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": test_database_name},
            )
            if database_exists is None:
                connection.execute(text(f'CREATE DATABASE "{test_database_name}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(autouse=True)
def _force_fake_ai_provider() -> Generator[None, None, None]:
    """Keep the whole suite on FakeAIProvider.

    ``backend/.env`` ships with ``AI_PROVIDER=soal`` for dev/demo use, which
    would otherwise resolve every ``get_provider(settings, provider="fake",
    ...)`` call to the real ``SoalProvider`` and make the suite depend on a
    live gate. Pinning the singleton ``settings.ai_provider`` to ``"fake"``
    keeps automated tests hermetic and deterministic; the dev server (reading
    the same ``.env`` at startup) still uses Soal. Tests that need a real
    provider construct their own ``Settings(...)`` explicitly and are marked
    ``soal`` (skipped unless ``SOAL_API_KEY`` is exported as an env var).
    """
    from app.core.config import settings

    original = settings.ai_provider
    settings.ai_provider = "fake"
    try:
        yield
    finally:
        settings.ai_provider = original


def _is_postgres_reachable(test_database_url: str) -> bool:
    import socket
    test_url = make_url(test_database_url)
    host = test_url.host or "localhost"
    port = test_url.port or 5432
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    from sqlalchemy.pool import StaticPool

    test_url = make_url(settings.test_database_url)
    engine = None
    if "sqlite" not in test_url.drivername and _is_postgres_reachable(settings.test_database_url):
        try:
            _ensure_test_database_exists(settings.test_database_url)
            pg_engine = create_engine(settings.test_database_url, pool_pre_ping=True)
            with pg_engine.connect():
                pass
            engine = pg_engine
        except Exception:
            engine = None

    if engine is None:
        from sqlalchemy import event

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

from collections.abc import Generator
import socket
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _is_db_reachable(db_url_str: str) -> bool:
    try:
        url = make_url(db_url_str)
        if "sqlite" in url.drivername:
            return True
        host = url.host or "localhost"
        port = url.port or 5432
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except Exception:
        return False


def _init_engine():
    db_url = settings.database_url
    if not _is_db_reachable(db_url):
        from pathlib import Path
        backend_dir = Path(__file__).resolve().parents[2]
        db_path = (backend_dir / "hera_dev.db").as_posix()
        db_url = f"sqlite:///{db_path}"

    connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
    eng = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    if "sqlite" in db_url:
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Ensure all tables exist on startup
        from app import models  # noqa: F401
        Base.metadata.create_all(bind=eng)

    return eng


engine = _init_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

from fastapi import FastAPI

from app.main import app


def test_fastapi_application_imports() -> None:
    assert isinstance(app, FastAPI)

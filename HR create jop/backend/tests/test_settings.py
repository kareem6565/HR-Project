import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_with_safe_test_configuration(tmp_path) -> None:
    storage_path = tmp_path / "test_storage"
    settings = Settings(
        APP_NAME="Test HR Assistant",
        APP_ENV="test",
        DEBUG=False,
        API_V1_PREFIX="/api/v1",
        DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/test_db",
        TEST_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/test_db_test",
        STORAGE_ROOT_DIR=str(storage_path),
        MAX_UPLOAD_BYTES=1_000_000,
    )

    assert settings.app_name == "Test HR Assistant"
    assert settings.app_env == "test"
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url == "postgresql+psycopg://user:password@localhost:5432/test_db"
    assert (
        settings.test_database_url
        == "postgresql+psycopg://user:password@localhost:5432/test_db_test"
    )
    assert settings.storage_root_dir == str(storage_path)
    assert settings.max_upload_bytes == 1_000_000


def production_settings(**overrides) -> Settings:
    values = {
        "APP_ENV": "production",
        "JWT_SECRET_KEY": "a-secure-production-jwt-secret-key-0001",
        "RESUME_ENCRYPTION_ENABLED": True,
        "RESUME_ENCRYPTION_KEY_ID": "primary",
        "RESUME_ENCRYPTION_KEYS": {"primary": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="},
        "GOOGLE_CALENDAR_MODE": "google",
        "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "https://example.test/oauth/callback",
        "GOOGLE_TOKEN_ENCRYPTION_KEY": "test-google-token-encryption-key-32chars",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_fake_ai_without_explicit_override() -> None:
    with pytest.raises(ValidationError, match="ALLOW_FAKE_AI=true"):
        production_settings(AI_PROVIDER="fake")


def test_production_allows_fake_ai_only_with_explicit_override() -> None:
    settings = production_settings(AI_PROVIDER="fake", ALLOW_FAKE_AI=True)
    assert settings.ai_provider == "fake"
    assert settings.allow_fake_ai is True


def test_fake_ai_remains_available_outside_production() -> None:
    settings = Settings(APP_ENV="test", AI_PROVIDER="fake")
    assert settings.ai_provider == "fake"

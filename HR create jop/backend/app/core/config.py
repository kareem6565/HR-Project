from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="AI HR Recruitment Assistant", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    database_url: str = Field(
        default="postgresql+psycopg://hr_ai_assistant:hr_ai_assistant@localhost:5432/hr_ai_assistant",
        validation_alias="DATABASE_URL",
    )
    test_database_url: str = Field(
        default="postgresql+psycopg://hr_ai_assistant:hr_ai_assistant@localhost:5432/hr_ai_assistant_test",
        validation_alias="TEST_DATABASE_URL",
    )
    storage_root_dir: str = Field(default="./storage", validation_alias="STORAGE_ROOT_DIR")
    ai_provider: Literal["fake", "soal", "ollama"] = Field(
        default="ollama", validation_alias="AI_PROVIDER"
    )
    soal_api_key: str | None = Field(default=None, validation_alias="SOAL_API_KEY")
    soal_base_url: str = Field(default="https://soal.help/api/v1", validation_alias="SOAL_BASE_URL")
    soal_model: str = Field(default="gemini-3.5-flash", validation_alias="SOAL_MODEL")
    ollama_api_key: str | None = Field(default=None, validation_alias="OLLAMA_API_KEY")
    ollama_base_url: str = Field(
        default="https://ollama.com/v1", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="gemma4:31b", validation_alias="OLLAMA_MODEL")
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, validation_alias="MAX_UPLOAD_BYTES")
    max_batch_files: int = Field(default=20, validation_alias="MAX_BATCH_FILES")
    max_batch_bytes: int = Field(default=50 * 1024 * 1024, validation_alias="MAX_BATCH_BYTES")
    max_pdf_pages: int = Field(default=50, validation_alias="MAX_PDF_PAGES")
    max_docx_uncompressed_bytes: int = Field(
        default=20 * 1024 * 1024, validation_alias="MAX_DOCX_UNCOMPRESSED_BYTES"
    )
    max_docx_entries: int = Field(default=100, validation_alias="MAX_DOCX_ENTRIES")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: Literal["json", "text"] = Field(default="json", validation_alias="LOG_FORMAT")
    cors_allow_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        validation_alias="CORS_ALLOW_ORIGINS",
    )
    cors_allow_methods: Literal["*"] | list[str] = Field(
        default=["GET", "POST", "PATCH", "DELETE"],
        validation_alias="CORS_ALLOW_METHODS",
    )
    jwt_secret_key: str = Field(
        default="",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, validation_alias="JWT_EXPIRE_MINUTES")
    jwt_issuer: str = Field(default="hera-auth", validation_alias="JWT_ISSUER")
    jwt_audience: str = Field(default="hera-api", validation_alias="JWT_AUDIENCE")
    hr_sso_shared_secret: str = Field(default="", validation_alias="HR_SSO_SHARED_SECRET")
    hr_sso_organization_id: str = Field(default="", validation_alias="HR_SSO_ORGANIZATION_ID")
    hr_sso_issuer: str = Field(default="hr-manager", validation_alias="HR_SSO_ISSUER")
    enable_screening_worker: bool = Field(default=True, validation_alias="ENABLE_SCREENING_WORKER")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        from pathlib import Path

        storage_path = Path(self.storage_root_dir)
        if not storage_path.is_absolute():
            backend_dir = Path(__file__).resolve().parents[2]
            self.storage_root_dir = str(backend_dir / "storage")

        known_weak_keys = {
            "dev-jwt-secret-key-not-for-production-min-32-chars",
            "change-me-to-a-secure-random-secret-key-32chars",
            "secret",
            "changeme",
        }
        if self.app_env == "production":
            if (
                not self.jwt_secret_key
                or self.jwt_secret_key in known_weak_keys
                or len(self.jwt_secret_key) < 32
            ):
                raise ValueError(
                    "A secure, non-default JWT_SECRET_KEY of at least 32 characters is "
                    "required in production."
                )
        elif self.app_env == "test":
            if not self.jwt_secret_key:
                # Tests may use an explicit test-only secret
                self.jwt_secret_key = "hera-test-explicit-jwt-secret-key-32chars-minimum"
        else:
            if not self.jwt_secret_key:
                raise ValueError(
                    "JWT_SECRET_KEY environment variable is required and must not be empty. "
                    "Set JWT_SECRET_KEY in your .env file or environment."
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

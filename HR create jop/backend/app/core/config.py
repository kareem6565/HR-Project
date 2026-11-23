from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
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
    resume_encryption_enabled: bool = Field(
        default=False, validation_alias="RESUME_ENCRYPTION_ENABLED"
    )
    resume_encryption_key_id: str = Field(default="", validation_alias="RESUME_ENCRYPTION_KEY_ID")
    resume_encryption_keys: dict[str, str] = Field(
        default_factory=dict, validation_alias="RESUME_ENCRYPTION_KEYS"
    )
    retention_enabled: bool = Field(default=False, validation_alias="RETENTION_ENABLED")
    retention_max_deletions_per_run: int = Field(
        default=100, ge=1, le=10000, validation_alias="RETENTION_MAX_DELETIONS_PER_RUN"
    )
    ai_provider: Literal["fake", "soal", "ollama", "openrouter", "local", "ollama_local"] = Field(
        default="openrouter", validation_alias="AI_PROVIDER"
    )
    ai_mode: Literal["llm", "rules"] = Field(default="llm", validation_alias="AI_MODE")
    a5_prerank_enabled: bool = Field(default=False, validation_alias="A5_PRERANK_ENABLED")
    a5_prerank_model_dir: str = Field(
        default="./models/multilingual-e5-small", validation_alias="A5_PRERANK_MODEL_DIR"
    )
    a5_prerank_threads: int = Field(default=2, ge=1, le=32, validation_alias="A5_PRERANK_THREADS")
    a5_prerank_max_chunks_per_cv: int = Field(
        default=24, ge=1, le=256, validation_alias="A5_PRERANK_MAX_CHUNKS_PER_CV"
    )
    a5_prerank_timeout_seconds: int = Field(
        default=45, ge=1, le=600, validation_alias="A5_PRERANK_TIMEOUT_SECONDS"
    )
    a5_prerank_quantized: bool = Field(default=False, validation_alias="A5_PRERANK_QUANTIZED")
    allow_fake_ai: bool = Field(default=False, validation_alias="ALLOW_FAKE_AI")
    soal_api_key: str | None = Field(default=None, validation_alias="SOAL_API_KEY")
    soal_base_url: str = Field(default="https://soal.help/api/v1", validation_alias="SOAL_BASE_URL")
    soal_model: str = Field(default="gemini-3.5-flash", validation_alias="SOAL_MODEL")
    ollama_api_key: str | None = Field(default=None, validation_alias="OLLAMA_API_KEY")
    ollama_base_url: str = Field(
        default="https://ollama.com/v1", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="gemma4:31b", validation_alias="OLLAMA_MODEL")
    local_llm_api_key: str | None = Field(default=None, validation_alias="LOCAL_LLM_API_KEY")
    local_llm_base_url: str = Field(
        default="http://localhost:8000/v1", validation_alias="LOCAL_LLM_BASE_URL"
    )
    local_llm_model: str = Field(default="", validation_alias="LOCAL_LLM_MODEL")
    ollama_local_base_url: str = Field(
        default="http://localhost:11434", validation_alias="OLLAMA_LOCAL_BASE_URL"
    )
    ollama_local_model: str = Field(default="", validation_alias="OLLAMA_LOCAL_MODEL")
    ollama_local_num_ctx: int = Field(
        default=16384, ge=2048, le=131072, validation_alias="OLLAMA_LOCAL_NUM_CTX"
    )
    ai_self_hosted_global_rpm_limit: int = Field(
        default=60, gt=0, validation_alias="AI_SELF_HOSTED_GLOBAL_RPM_LIMIT"
    )
    ai_self_hosted_global_daily_limit: int = Field(
        default=1000, gt=0, validation_alias="AI_SELF_HOSTED_GLOBAL_DAILY_LIMIT"
    )
    ai_self_hosted_user_rpm_limit: int = Field(
        default=30, gt=0, validation_alias="AI_SELF_HOSTED_USER_RPM_LIMIT"
    )
    ai_self_hosted_user_daily_limit: int = Field(
        default=300, gt=0, validation_alias="AI_SELF_HOSTED_USER_DAILY_LIMIT"
    )
    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL"
    )
    openrouter_model: str = Field(default="openrouter/free", validation_alias="OPENROUTER_MODEL")
    openrouter_max_tokens: int = Field(
        default=4096, gt=0, le=32768, validation_alias="OPENROUTER_MAX_TOKENS"
    )
    ai_free_model_allowlist: str = Field(default="", validation_alias="AI_FREE_MODEL_ALLOWLIST")
    ai_paid_mode_enabled: bool = Field(default=False, validation_alias="AI_PAID_MODE_ENABLED")
    ai_paid_budget_usd: float = Field(default=0.0, ge=0, validation_alias="AI_PAID_BUDGET_USD")
    ai_global_rpm_limit: int = Field(default=15, gt=0, validation_alias="AI_GLOBAL_RPM_LIMIT")
    ai_global_daily_limit: int = Field(default=40, gt=0, validation_alias="AI_GLOBAL_DAILY_LIMIT")
    ai_user_rpm_limit: int = Field(default=5, gt=0, validation_alias="AI_USER_RPM_LIMIT")
    ai_user_daily_limit: int = Field(default=20, gt=0, validation_alias="AI_USER_DAILY_LIMIT")
    ai_tester_user_ids: str = Field(default="", validation_alias="AI_TESTER_USER_IDS")
    ai_tester_user_rpm_limit: int = Field(
        default=10, gt=0, validation_alias="AI_TESTER_USER_RPM_LIMIT"
    )
    ai_tester_user_daily_limit: int = Field(
        default=60, gt=0, validation_alias="AI_TESTER_USER_DAILY_LIMIT"
    )
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
    allow_local_login: bool = Field(default=False, validation_alias="ALLOW_LOCAL_LOGIN")
    enable_screening_worker: bool = Field(default=True, validation_alias="ENABLE_SCREENING_WORKER")
    apify_api_token: str | None = Field(default=None, validation_alias="APIFY_API_TOKEN")
    apify_linkedin_jobs_actor_id: str = Field(
        default="fetch_cat/linkedin-jobs-scraper",
        validation_alias="APIFY_LINKEDIN_JOBS_ACTOR_ID",
    )
    apify_import_enabled: bool = Field(default=False, validation_alias="APIFY_IMPORT_ENABLED")
    application_privacy_notice_text: str = Field(
        default="", validation_alias="APPLICATION_PRIVACY_NOTICE_TEXT"
    )
    application_privacy_notice_version: str = Field(
        default="", validation_alias="APPLICATION_PRIVACY_NOTICE_VERSION"
    )
    application_privacy_notice_approved: bool = Field(
        default=False, validation_alias="APPLICATION_PRIVACY_NOTICE_APPROVED"
    )
    turnstile_required: bool = Field(default=False, validation_alias="TURNSTILE_REQUIRED")
    turnstile_secret_key: str = Field(default="", validation_alias="TURNSTILE_SECRET_KEY")
    turnstile_expected_hostname: str = Field(
        default="", validation_alias="TURNSTILE_EXPECTED_HOSTNAME"
    )
    public_application_rate_limit: int = Field(
        default=5, validation_alias="PUBLIC_APPLICATION_RATE_LIMIT"
    )
    public_application_rate_window_seconds: int = Field(
        default=3600, validation_alias="PUBLIC_APPLICATION_RATE_WINDOW_SECONDS"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_storage_security(self) -> "Settings":
        import base64
        import binascii
        import re

        if (
            self.app_env.lower() == "production"
            and self.ai_provider == "fake"
            and not self.allow_fake_ai
        ):
            raise ValueError(
                "AI_PROVIDER=fake is not allowed in production unless ALLOW_FAKE_AI=true."
            )
        if self.app_env.lower() == "production" and not self.resume_encryption_enabled:
            raise ValueError("RESUME_ENCRYPTION_ENABLED=true is required in production.")
        if not self.resume_encryption_enabled:
            return self
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", self.resume_encryption_key_id):
            raise ValueError(
                "A valid RESUME_ENCRYPTION_KEY_ID is required when encryption is enabled."
            )
        encoded_key = self.resume_encryption_keys.get(self.resume_encryption_key_id)
        if not encoded_key:
            raise ValueError(
                "RESUME_ENCRYPTION_KEYS must contain the active key id when encryption is enabled."
            )
        try:
            active_key = base64.b64decode(encoded_key, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("The active resume encryption key must be valid base64.") from None
        if len(active_key) != 32:
            raise ValueError("The active resume encryption key must decode to exactly 32 bytes.")
        return self

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

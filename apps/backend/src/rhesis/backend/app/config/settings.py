from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus, urlparse

from pydantic import AnyHttpUrl, Field, TypeAdapter, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration built from component environment variables.

    Host/port/name default to the local dev database (postgres on
    localhost:5432/rhesis-db, matching docker-compose and ``./rh dev up``).
    Credentials have no default and must always be provided via .env or
    other config, in any environment.

    Runtime (app) URL uses APP_DB_USER / APP_DB_PASS.
    Migration (admin) URL uses ADMIN_DB_USER / ADMIN_DB_PASS, falling back to
    the app credentials when the admin vars are not set (single-role setups).
    Migration-only jobs may omit APP_DB_* when ADMIN_DB_* is set.
    """

    model_config = SettingsConfigDict(env_ignore_empty=True)

    driver: str = Field(default="postgresql", alias="DB_DRIVER")
    host: str = Field(default="localhost", alias="DB_HOST")
    port: int = Field(default=5432, alias="DB_PORT")
    name: str = Field(default="rhesis-db", alias="DB_NAME")

    app_user: str | None = Field(default=None, alias="APP_DB_USER")
    app_password: str | None = Field(default=None, alias="APP_DB_PASS")
    admin_user: str | None = Field(default=None, alias="ADMIN_DB_USER")
    admin_password: str | None = Field(default=None, alias="ADMIN_DB_PASS")

    @model_validator(mode="after")
    def _validate_credentials(self) -> "DatabaseSettings":
        if self.app_user is not None and self.app_password is None:
            raise ValueError("APP_DB_USER is set but APP_DB_PASS is missing")
        if self.admin_user is not None and self.admin_password is None:
            raise ValueError("ADMIN_DB_USER is set but ADMIN_DB_PASS is missing")
        return self

    def _build_url(self, user: str, password: str) -> str:
        user_q = quote_plus(user)
        pw_q = quote_plus(password)
        if self.host.startswith("/"):
            return f"{self.driver}://{user_q}:{pw_q}@/{self.name}?host={self.host}"
        return f"{self.driver}://{user_q}:{pw_q}@{self.host}:{self.port}/{self.name}"

    @property
    def app_url(self) -> str:
        if self.app_user is None or self.app_password is None:
            raise ValueError("APP_DB_USER and APP_DB_PASS are required for runtime database access")
        return self._build_url(self.app_user, self.app_password)

    @property
    def admin_url(self) -> str:
        if self.admin_user is not None and self.admin_password is not None:
            return self._build_url(self.admin_user, self.admin_password)
        if self.app_user is not None and self.app_password is not None:
            return self._build_url(self.app_user, self.app_password)
        raise ValueError("No database credentials configured (set ADMIN_DB_* or APP_DB_*)")


class FrontendSettings(BaseSettings):
    """Frontend application configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        TypeAdapter(AnyHttpUrl).validate_python(value)
        return value

    @property
    def cors_origins(self) -> list[str]:
        parsed_url = urlparse(self.url)
        return [f"{parsed_url.scheme}://{parsed_url.netloc}"]

    @property
    def allowed_domain(self) -> str:
        return urlparse(self.url).netloc

    @property
    def loopback_cors_regex(self) -> str | None:
        if get_application_settings().is_development:
            return r"^http://(localhost|127\.0\.0\.1|\[::1\])(:\d{1,5})?$"
        return None


class ApplicationSettings(BaseSettings):
    """General application runtime configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    quick_start: bool = Field(default=False, alias="QUICK_START")
    backend_env: Literal["production", "development", "staging", "local"] = Field(
        default="development", alias="BACKEND_ENV"
    )
    # Google Cloud-specific environment variables set by Google Cloud runtimes.
    gcp_project: str | None = Field(default=None, alias="GCP_PROJECT")
    google_cloud_project: str | None = Field(default=None, alias="GOOGLE_CLOUD_PROJECT")
    cloud_run_service: str | None = Field(default=None, alias="K_SERVICE")
    cloud_run_revision: str | None = Field(default=None, alias="K_REVISION")
    api_base_url: str = Field(default="http://localhost:8080", alias="API_BASE_URL")

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str) -> str:
        TypeAdapter(AnyHttpUrl).validate_python(value)
        return value

    @field_validator("backend_env", mode="before")
    @classmethod
    def normalize_environment_value(cls, value: str) -> str:
        return value.lower()

    @property
    def is_production(self) -> bool:
        return self.backend_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return not self.is_production

    @property
    def is_google_cloud(self) -> bool:
        return bool(self.cloud_run_service or self.cloud_run_revision)

    @property
    def quick_start_allowed_by_env(self) -> bool:
        """Whether process-level configuration permits Quick Start mode.

        This is the deployment-static portion of the Quick Start gate: it is
        fail-secure and returns False if QUICK_START is not explicitly enabled,
        if BACKEND_ENV is production, or if any Google Cloud signal is present.
        Request-scoped signals
        (hostname, headers) are evaluated separately in
        ``rhesis.backend.app.utils.quick_start.is_quick_start_enabled``.
        """
        if not self.quick_start:
            return False
        if self.is_production:
            return False
        if self.is_google_cloud:
            return False
        if self.gcp_project or self.google_cloud_project:
            return False
        return True


class TelemetrySettings(BaseSettings):
    """OpenTelemetry export and deployment metadata configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    otlp_endpoint: str = Field(
        default="https://telemetry.rhesis.ai",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    service_name: str = Field(default="rhesis", alias="OTEL_SERVICE_NAME")
    deployment_type: str = Field(default="self-hosted", alias="OTEL_DEPLOYMENT_TYPE")
    rhesis_telemetry_enabled: bool = Field(
        default=True,
        alias="OTEL_RHESIS_TELEMETRY_ENABLED",
    )


class LoggingSettings(BaseSettings):
    """Logging configuration and runtime environment detection."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: str = Field(default="logs", alias="LOG_DIR")


class AuthSettings(BaseSettings):
    """Authentication provider and session configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    email_password_enabled: bool = Field(default=True, alias="AUTH_EMAIL_PASSWORD_ENABLED")
    registration_enabled: bool = Field(default=True, alias="AUTH_REGISTRATION_ENABLED")
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    github_client_id: str | None = Field(default=None, alias="GH_CLIENT_ID")
    github_client_secret: str | None = Field(default=None, alias="GH_CLIENT_SECRET")
    session_secret_key: str | None = Field(default=None, alias="SESSION_SECRET_KEY")
    jwt_secret_key: str | None = Field(default=None, alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=10080,
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)


class RedisSettings(BaseSettings):
    """Redis broker configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    broker_url: str = Field(default="redis://localhost:6379/0", alias="BROKER_URL")
    broker_read_url: str | None = Field(default=None, alias="BROKER_READ_URL")
    result_backend: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_RESULT_BACKEND",
    )


class StorageSettings(BaseSettings):
    """Object storage configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    service_uri: str | None = Field(default="file:///app/storage", alias="STORAGE_SERVICE_URI")
    service_account_key: str | None = Field(default=None, alias="STORAGE_SERVICE_ACCOUNT_KEY")
    local_storage_path: str = Field(default="/tmp/rhesis-files", alias="LOCAL_STORAGE_PATH")


class SMTPSettings(BaseSettings):
    """SMTP email delivery configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    host: str | None = Field(default=None, alias="SMTP_HOST")
    port: int = Field(default=587, alias="SMTP_PORT")
    user: str | None = Field(default=None, alias="SMTP_USER")
    password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    from_email: str = Field(default="engineering@rhesis.ai", alias="FROM_EMAIL")


class ModelSettings(BaseSettings):
    """Default model configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    generation_model: str = Field(
        default="rhesis/rhesis-default",
        alias="DEFAULT_GENERATION_MODEL",
    )
    evaluation_model: str = Field(
        default="rhesis/rhesis-default",
        alias="DEFAULT_EVALUATION_MODEL",
    )
    execution_model: str = Field(
        default="rhesis/rhesis-default",
        alias="DEFAULT_EXECUTION_MODEL",
    )
    embedding_model: str = Field(
        default="rhesis/rhesis-embedding",
        alias="DEFAULT_EMBEDDING_MODEL",
    )


class RhesisSettings(BaseSettings):
    """Rhesis platform API configuration for hosted models (not deployment callbacks)."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    base_url: str = Field(default="https://api.rhesis.ai", alias="RHESIS_BASE_URL")
    api_key: str | None = Field(default=None, alias="RHESIS_API_KEY")


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    return FrontendSettings()  # pyright: ignore[reportCallIssue]


@lru_cache
def get_application_settings() -> ApplicationSettings:
    return ApplicationSettings()


@lru_cache
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()


@lru_cache
def get_redis_settings() -> RedisSettings:
    return RedisSettings()


@lru_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()


@lru_cache
def get_smtp_settings() -> SMTPSettings:
    return SMTPSettings()


@lru_cache
def get_model_settings() -> ModelSettings:
    return ModelSettings()


@lru_cache
def get_rhesis_settings() -> RhesisSettings:
    return RhesisSettings()


@lru_cache
def get_telemetry_settings() -> TelemetrySettings:
    return TelemetrySettings()

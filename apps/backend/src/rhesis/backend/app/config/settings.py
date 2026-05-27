from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, AnyHttpUrl, Field, TypeAdapter, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration loaded from SQLALCHEMY_DATABASE_URL."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    url: str = Field(alias="SQLALCHEMY_DATABASE_URL")


class FrontendSettings(BaseSettings):
    """Frontend application configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    url: str = Field(alias="FRONTEND_URL")

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


class RedisSettings(BaseSettings):
    """Redis broker configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    broker_url: str = Field(default="redis://localhost:6379/0", alias="BROKER_URL")
    broker_read_url: str | None = Field(default=None, alias="BROKER_READ_URL")
    result_backend: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_RESULT_BACKEND",
    )


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


class ApplicationSettings(BaseSettings):
    """General application runtime configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    quick_start: bool = Field(default=False, alias="QUICK_START")
    environment: str = Field(
        default="",
        validation_alias=AliasChoices("ENVIRONMENT", "ENV"),
    )
    backend_env: str = Field(default="development", alias="BACKEND_ENV")
    # Google Cloud-specific environment variables set by Google Cloud runtimes.
    gcp_project: str | None = Field(default=None, alias="GCP_PROJECT")
    google_cloud_project: str | None = Field(default=None, alias="GOOGLE_CLOUD_PROJECT")
    cloud_run_service: str | None = Field(default=None, alias="K_SERVICE")
    cloud_run_revision: str | None = Field(default=None, alias="K_REVISION")

    @property
    def is_production(self) -> bool:
        return self.backend_env.lower() == "production" or self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        return not self.is_production


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()  # pyright: ignore[reportCallIssue]


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    return FrontendSettings()  # pyright: ignore[reportCallIssue]


@lru_cache
def get_redis_settings() -> RedisSettings:
    return RedisSettings()


@lru_cache
def get_model_settings() -> ModelSettings:
    return ModelSettings()


@lru_cache
def get_application_settings() -> ApplicationSettings:
    return ApplicationSettings()

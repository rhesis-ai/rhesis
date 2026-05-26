from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration loaded from SQLALCHEMY_DATABASE_URL."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    url: str = Field(alias="SQLALCHEMY_DATABASE_URL")


class FrontendSettings(BaseSettings):
    """Frontend application configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    url: AnyHttpUrl = Field(alias="FRONTEND_URL")

    @property
    def cors_origins(self) -> list[str]:
        parsed_url = urlparse(str(self.url))
        return [f"{parsed_url.scheme}://{parsed_url.netloc}"]

    @property
    def allowed_domain(self) -> str:
        return urlparse(str(self.url)).netloc


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

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration loaded from SQLALCHEMY_DATABASE_URL."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    url: str = Field(alias="SQLALCHEMY_DATABASE_URL")


class FrontendSettings(BaseSettings):
    """Frontend application configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")

    @property
    def cors_origins(self) -> list[str]:
        return [self.url.rstrip("/")]

    @property
    def allowed_domain(self) -> str:
        return urlparse(self.url).netloc


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()  # pyright: ignore[reportCallIssue]


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    return FrontendSettings()

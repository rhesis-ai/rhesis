from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration loaded from SQLALCHEMY_DATABASE_URL."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    url: str = Field(alias="SQLALCHEMY_DATABASE_URL")


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()

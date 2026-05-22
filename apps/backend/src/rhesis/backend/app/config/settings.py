from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration loaded from SQLALCHEMY_DATABASE_URL."""

    url: str = Field(alias="SQLALCHEMY_DATABASE_URL")


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()

import pytest
from pydantic import ValidationError

from rhesis.backend.app import database
from rhesis.backend.app.config.settings import DatabaseSettings

DATABASE_ENV_VARS = ("SQLALCHEMY_DATABASE_URL",)


@pytest.fixture
def clean_database_env(monkeypatch):
    for env_var in DATABASE_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


@pytest.mark.unit
def test_database_url_is_required(clean_database_env):
    with pytest.raises(ValidationError, match="SQLALCHEMY_DATABASE_URL"):
        DatabaseSettings(_env_file=None)


@pytest.mark.unit
def test_database_settings_loads_existing_environment_variables(clean_database_env, monkeypatch):
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URL", "postgresql://prod")

    settings = DatabaseSettings(_env_file=None)

    assert settings.url == "postgresql://prod"


def _patch_database_settings(monkeypatch, **settings_values):
    if "url" in settings_values:
        settings_values["SQLALCHEMY_DATABASE_URL"] = settings_values.pop("url")

    settings = DatabaseSettings(_env_file=None, **settings_values)
    monkeypatch.setattr(database, "get_database_settings", lambda: settings)
    return database


@pytest.mark.unit
def test_get_database_url_returns_configured_url(clean_database_env, monkeypatch):
    database = _patch_database_settings(
        monkeypatch,
        url="postgresql://direct-user:direct-pass@db.example.com:5432/direct-db",  #  trufflehog:ignore
    )

    assert (
        database.get_database_url()
        == "postgresql://direct-user:direct-pass@db.example.com:5432/direct-db"  # trufflehog:ignore
    )


@pytest.mark.unit
def test_database_url_comes_from_sqlalchemy_database_url(clean_database_env, monkeypatch):
    database = _patch_database_settings(
        monkeypatch,
        url="postgresql://test-user:test-pass@localhost:5432/test-db",  # trufflehog:ignore
    )

    assert (
        database.get_database_url()
        == "postgresql://test-user:test-pass@localhost:5432/test-db"  # trufflehog:ignore
    )

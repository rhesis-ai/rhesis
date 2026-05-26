import pytest
from pydantic import ValidationError

from rhesis.backend.app import database
from rhesis.backend.app.config.settings import (
    DatabaseSettings,
    FrontendSettings,
    ModelSettings,
    RedisSettings,
    get_frontend_settings,
    get_model_settings,
    get_redis_settings,
)

DATABASE_ENV_VARS = ("SQLALCHEMY_DATABASE_URL",)
FRONTEND_ENV_VARS = ("FRONTEND_URL",)
REDIS_ENV_VARS = ("BROKER_URL", "BROKER_READ_URL", "CELERY_RESULT_BACKEND")
MODEL_ENV_VARS = (
    "DEFAULT_GENERATION_MODEL",
    "DEFAULT_EVALUATION_MODEL",
    "DEFAULT_EXECUTION_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
)


@pytest.fixture
def clean_database_env(monkeypatch):
    for env_var in DATABASE_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


@pytest.fixture
def clean_frontend_env(monkeypatch):
    for env_var in FRONTEND_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_frontend_settings.cache_clear()
    yield
    get_frontend_settings.cache_clear()


@pytest.fixture
def clean_redis_env(monkeypatch):
    for env_var in REDIS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_redis_settings.cache_clear()
    yield
    get_redis_settings.cache_clear()


@pytest.fixture
def clean_model_env(monkeypatch):
    for env_var in MODEL_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_model_settings.cache_clear()
    yield
    get_model_settings.cache_clear()


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


@pytest.mark.unit
def test_frontend_url_is_required(clean_frontend_env):
    with pytest.raises(ValidationError, match="FRONTEND_URL"):
        FrontendSettings(_env_file=None)


@pytest.mark.unit
def test_frontend_settings_validates_url(clean_frontend_env, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "not-a-url")

    with pytest.raises(ValidationError):
        FrontendSettings(_env_file=None)


@pytest.mark.unit
def test_frontend_settings_loads_existing_environment_variables(clean_frontend_env, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com")

    settings = FrontendSettings(_env_file=None)

    assert settings.url == "https://frontend.example.com"
    assert settings.cors_origins == ["https://frontend.example.com"]
    assert settings.allowed_domain == "frontend.example.com"


@pytest.mark.unit
def test_frontend_settings_normalizes_cors_origin_trailing_slash(
    clean_frontend_env,
    monkeypatch,
):
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/")

    settings = FrontendSettings(_env_file=None)

    assert settings.url == "https://frontend.example.com/"
    assert settings.cors_origins == ["https://frontend.example.com"]
    assert settings.allowed_domain == "frontend.example.com"


@pytest.mark.unit
def test_get_frontend_settings_cache_clear_allows_env_overrides(clean_frontend_env, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://initial.example.com")

    assert get_frontend_settings().url == "https://initial.example.com"

    monkeypatch.setenv("FRONTEND_URL", "https://cached.example.com")
    get_frontend_settings.cache_clear()

    assert get_frontend_settings().url == "https://cached.example.com"
    assert get_frontend_settings().cors_origins == ["https://cached.example.com"]
    assert get_frontend_settings().allowed_domain == "cached.example.com"


@pytest.mark.unit
def test_redis_settings_uses_local_defaults(clean_redis_env):
    settings = RedisSettings(_env_file=None)

    assert settings.broker_url == "redis://localhost:6379/0"
    assert settings.broker_read_url is None
    assert settings.result_backend == "redis://localhost:6379/1"


@pytest.mark.unit
def test_redis_settings_loads_existing_environment_variables(clean_redis_env, monkeypatch):
    monkeypatch.setenv("BROKER_URL", "redis://redis.example.com:6379/0")
    monkeypatch.setenv("BROKER_READ_URL", "redis://redis-read.example.com:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://redis.example.com:6379/1")

    settings = RedisSettings(_env_file=None)

    assert settings.broker_url == "redis://redis.example.com:6379/0"
    assert settings.broker_read_url == "redis://redis-read.example.com:6379/0"
    assert settings.result_backend == "redis://redis.example.com:6379/1"


@pytest.mark.unit
def test_get_redis_settings_cache_clear_allows_env_overrides(clean_redis_env, monkeypatch):
    assert get_redis_settings().broker_url == "redis://localhost:6379/0"

    monkeypatch.setenv("BROKER_URL", "redis://cached.example.com:6379/0")
    get_redis_settings.cache_clear()

    assert get_redis_settings().broker_url == "redis://cached.example.com:6379/0"


@pytest.mark.unit
def test_model_settings_uses_system_defaults(clean_model_env):
    settings = ModelSettings(_env_file=None)

    assert settings.generation_model == "rhesis/rhesis-default"
    assert settings.evaluation_model == "rhesis/rhesis-default"
    assert settings.execution_model == "rhesis/rhesis-default"
    assert settings.embedding_model == "rhesis/rhesis-embedding"


@pytest.mark.unit
def test_model_settings_loads_existing_environment_variables(clean_model_env, monkeypatch):
    monkeypatch.setenv("DEFAULT_GENERATION_MODEL", "openai/gpt-4o")
    monkeypatch.setenv("DEFAULT_EVALUATION_MODEL", "anthropic/claude-3-5-sonnet")
    monkeypatch.setenv("DEFAULT_EXECUTION_MODEL", "gemini/gemini-2.0-flash")
    monkeypatch.setenv("DEFAULT_EMBEDDING_MODEL", "openai/text-embedding-3-small")

    settings = ModelSettings(_env_file=None)

    assert settings.generation_model == "openai/gpt-4o"
    assert settings.evaluation_model == "anthropic/claude-3-5-sonnet"
    assert settings.execution_model == "gemini/gemini-2.0-flash"
    assert settings.embedding_model == "openai/text-embedding-3-small"


@pytest.mark.unit
def test_get_model_settings_cache_clear_allows_env_overrides(clean_model_env, monkeypatch):
    assert get_model_settings().generation_model == "rhesis/rhesis-default"

    monkeypatch.setenv("DEFAULT_GENERATION_MODEL", "openai/gpt-4o-mini")
    get_model_settings.cache_clear()

    assert get_model_settings().generation_model == "openai/gpt-4o-mini"

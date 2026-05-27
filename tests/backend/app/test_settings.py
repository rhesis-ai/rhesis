import re

import pytest
from pydantic import ValidationError

from rhesis.backend.app import database
from rhesis.backend.app.config.settings import (
    ApplicationSettings,
    DatabaseSettings,
    FrontendSettings,
    ModelSettings,
    RedisSettings,
    get_application_settings,
    get_frontend_settings,
    get_model_settings,
    get_redis_settings,
)

DATABASE_ENV_VARS = ("SQLALCHEMY_DATABASE_URL",)
FRONTEND_ENV_VARS = ("FRONTEND_URL",)
APPLICATION_ENV_VARS = (
    "QUICK_START",
    "ENVIRONMENT",
    "ENV",
    "BACKEND_ENV",
    "GCP_PROJECT",
    "GOOGLE_CLOUD_PROJECT",
    "K_SERVICE",
    "K_REVISION",
)
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
def clean_application_env(monkeypatch):
    for env_var in APPLICATION_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_application_settings.cache_clear()
    yield
    get_application_settings.cache_clear()


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


@pytest.mark.unit
def test_application_settings_defaults(clean_application_env):
    """All fields use their declared defaults when no env vars are set."""
    settings = ApplicationSettings(_env_file=None)

    assert settings.quick_start is False
    assert settings.environment == ""
    assert settings.backend_env == "development"
    assert settings.gcp_project is None
    assert settings.google_cloud_project is None
    assert settings.cloud_run_service is None
    assert settings.cloud_run_revision is None
    # Default posture is non-production (dev-only affordances are on by
    # default, matching utils/git_utils.should_show_git_info).
    assert settings.is_production is False
    assert settings.is_development is True


@pytest.mark.unit
def test_application_settings_loads_existing_environment_variables(
    clean_application_env, monkeypatch
):
    monkeypatch.setenv("QUICK_START", "true")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("BACKEND_ENV", "production")
    monkeypatch.setenv("GCP_PROJECT", "rhesis-prod")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "rhesis-prod-2")
    monkeypatch.setenv("K_SERVICE", "rhesis-backend")
    monkeypatch.setenv("K_REVISION", "rhesis-backend-00042-abc")

    settings = ApplicationSettings(_env_file=None)

    assert settings.quick_start is True
    assert settings.environment == "staging"
    assert settings.backend_env == "production"
    assert settings.gcp_project == "rhesis-prod"
    assert settings.google_cloud_project == "rhesis-prod-2"
    assert settings.cloud_run_service == "rhesis-backend"
    assert settings.cloud_run_revision == "rhesis-backend-00042-abc"


@pytest.mark.unit
def test_application_settings_environment_alias_choice_env(clean_application_env, monkeypatch):
    """ENVIRONMENT and ENV are equivalent aliases for the same field."""
    monkeypatch.setenv("ENV", "production")

    settings = ApplicationSettings(_env_file=None)

    assert settings.environment == "production"
    assert settings.is_production is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "backend_env,environment,expected_is_production",
    [
        # Either signal being production wins.
        ("production", "", True),
        ("development", "production", True),
        ("PRODUCTION", "", True),
        # Neither signal being production -> not production.
        ("development", "", False),
        ("local", "", False),
        ("development", "staging", False),
        ("", "", False),
    ],
)
def test_application_settings_is_production_or_logic(
    clean_application_env, monkeypatch, backend_env, environment, expected_is_production
):
    """is_production fires when EITHER backend_env or environment is production."""
    if backend_env:
        monkeypatch.setenv("BACKEND_ENV", backend_env)
    if environment:
        monkeypatch.setenv("ENVIRONMENT", environment)

    settings = ApplicationSettings(_env_file=None)

    assert settings.is_production is expected_is_production
    assert settings.is_development is (not expected_is_production)


@pytest.mark.unit
def test_get_application_settings_cache_clear_allows_env_overrides(
    clean_application_env, monkeypatch
):
    assert get_application_settings().is_development is True

    monkeypatch.setenv("BACKEND_ENV", "production")
    get_application_settings.cache_clear()

    assert get_application_settings().is_development is False
    assert get_application_settings().backend_env == "production"


@pytest.mark.unit
class TestLoopbackCorsRegex:
    """``FrontendSettings.loopback_cors_regex`` returns a regex only on dev backends.

    Mirrors the loopback redirect gate in ``auth/url_utils.py`` so that
    a frontend dev server on the developer's loopback can call a remote
    dev backend (FRONTEND_URL on a different host) without CORS blocking
    XHR/fetch requests.
    """

    @pytest.fixture(autouse=True)
    def _frontend_url(self, clean_frontend_env, monkeypatch):
        monkeypatch.setenv("FRONTEND_URL", "https://dev-app.rhesis.ai")

    def test_returns_none_in_production(self, clean_application_env, monkeypatch):
        monkeypatch.setenv("BACKEND_ENV", "production")
        get_application_settings.cache_clear()

        assert get_frontend_settings().loopback_cors_regex is None

    def test_returns_none_when_environment_is_production(
        self, clean_application_env, monkeypatch
    ):
        """ENVIRONMENT=production wins over BACKEND_ENV=development."""
        monkeypatch.setenv("BACKEND_ENV", "development")
        monkeypatch.setenv("ENVIRONMENT", "production")
        get_application_settings.cache_clear()

        assert get_frontend_settings().loopback_cors_regex is None

    def test_returns_regex_in_development(self, clean_application_env, monkeypatch):
        monkeypatch.setenv("BACKEND_ENV", "development")
        get_application_settings.cache_clear()

        regex = get_frontend_settings().loopback_cors_regex

        assert regex is not None
        compiled = re.compile(regex)
        assert compiled.match("http://localhost:3000")
        assert compiled.match("http://localhost:5173")
        assert compiled.match("http://127.0.0.1:8080")
        assert compiled.match("http://[::1]:5000")
        assert compiled.match("http://localhost")  # default port

    def test_regex_rejects_lookalikes(self, clean_application_env, monkeypatch):
        """The regex must not match localhost-themed lookalike origins."""
        monkeypatch.setenv("BACKEND_ENV", "development")
        get_application_settings.cache_clear()

        regex = get_frontend_settings().loopback_cors_regex
        assert regex is not None
        compiled = re.compile(regex)

        # Substring/suffix attacks must not slip through.
        assert not compiled.match("http://evil-localhost.com")
        assert not compiled.match("http://localhost.attacker.com")
        assert not compiled.match("http://127.0.0.1.attacker.com")
        # https on loopback is not honoured (devs serving https locally
        # would need to register their origin via FRONTEND_URL instead).
        assert not compiled.match("https://localhost:3000")
        # Other private ranges are not loopback.
        assert not compiled.match("http://10.0.0.1:3000")
        assert not compiled.match("http://192.168.1.1:3000")

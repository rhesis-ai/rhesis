import pytest
from pydantic import ValidationError

from rhesis.backend.app import database
from rhesis.backend.app.config.settings import (
    ApplicationSettings,
    AuthSettings,
    DatabaseSettings,
    FrontendSettings,
    ModelSettings,
    RedisSettings,
    RhesisSettings,
    SMTPSettings,
    StorageSettings,
    TelemetrySettings,
    get_application_settings,
    get_auth_settings,
    get_database_settings,
    get_frontend_settings,
    get_model_settings,
    get_redis_settings,
    get_rhesis_settings,
    get_smtp_settings,
    get_storage_settings,
    get_telemetry_settings,
)
from rhesis.backend.notifications.email.smtp import SMTPService

DATABASE_ENV_VARS = (
    "DB_DRIVER",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "APP_DB_USER",
    "APP_DB_PASS",
    "ADMIN_DB_USER",
    "ADMIN_DB_PASS",
)
FRONTEND_ENV_VARS = ("FRONTEND_URL",)
APPLICATION_ENV_VARS = (
    "QUICK_START",
    "BACKEND_ENV",
    "API_BASE_URL",
    "GCP_PROJECT",
    "GOOGLE_CLOUD_PROJECT",
    "K_SERVICE",
    "K_REVISION",
)
AUTH_ENV_VARS = (
    "AUTH_EMAIL_PASSWORD_ENABLED",
    "AUTH_REGISTRATION_ENABLED",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GH_CLIENT_ID",
    "GH_CLIENT_SECRET",
    "SESSION_SECRET_KEY",
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
)
REDIS_ENV_VARS = ("BROKER_URL", "BROKER_READ_URL", "CELERY_RESULT_BACKEND")
STORAGE_ENV_VARS = ("STORAGE_SERVICE_URI", "STORAGE_SERVICE_ACCOUNT_KEY", "LOCAL_STORAGE_PATH")
SMTP_ENV_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL")
MODEL_ENV_VARS = (
    "DEFAULT_GENERATION_MODEL",
    "DEFAULT_EVALUATION_MODEL",
    "DEFAULT_EXECUTION_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
)
RHESIS_ENV_VARS = ("RHESIS_BASE_URL", "RHESIS_API_KEY")
TELEMETRY_ENV_VARS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "OTEL_DEPLOYMENT_TYPE",
    "OTEL_RHESIS_TELEMETRY_ENABLED",
)

_BASE_DB_ENV = {
    "DB_HOST": "localhost",
    "DB_NAME": "testdb",
    "APP_DB_USER": "app-user",
    "APP_DB_PASS": "app-pass",  # trufflehog:ignore
}


@pytest.fixture
def clean_database_env(monkeypatch):
    for env_var in DATABASE_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_database_settings.cache_clear()
    yield
    get_database_settings.cache_clear()


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
def minimal_application_env(clean_application_env, monkeypatch):
    """Sets API_BASE_URL to a distinct test value (default is http://localhost:8080)."""
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    yield


@pytest.fixture
def clean_auth_env(monkeypatch):
    for env_var in AUTH_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_auth_settings.cache_clear()
    yield
    get_auth_settings.cache_clear()


@pytest.fixture
def clean_redis_env(monkeypatch):
    for env_var in REDIS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_redis_settings.cache_clear()
    yield
    get_redis_settings.cache_clear()


@pytest.fixture
def clean_storage_env(monkeypatch):
    for env_var in STORAGE_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_storage_settings.cache_clear()
    yield
    get_storage_settings.cache_clear()


@pytest.fixture
def clean_smtp_env(monkeypatch):
    for env_var in SMTP_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_smtp_settings.cache_clear()
    yield
    get_smtp_settings.cache_clear()


@pytest.fixture
def clean_model_env(monkeypatch):
    for env_var in MODEL_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_model_settings.cache_clear()
    yield
    get_model_settings.cache_clear()


@pytest.fixture
def clean_rhesis_env(monkeypatch):
    for env_var in RHESIS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_rhesis_settings.cache_clear()
    yield
    get_rhesis_settings.cache_clear()


@pytest.fixture
def clean_telemetry_env(monkeypatch):
    for env_var in TELEMETRY_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    get_telemetry_settings.cache_clear()
    yield
    get_telemetry_settings.cache_clear()


@pytest.mark.unit
def test_database_settings_uses_dev_defaults_when_env_missing(clean_database_env):
    """With no DB_* vars set, host/port/name default to the local dev database."""
    settings = DatabaseSettings(_env_file=None)

    assert settings.host == "localhost"
    assert settings.port == 5432
    assert settings.name == "rhesis-db"
    assert settings.app_user is None
    assert settings.app_password is None


@pytest.mark.unit
def test_database_app_credentials_are_required(clean_database_env):
    """Credentials have no default and must always be provided explicitly."""
    settings = DatabaseSettings(_env_file=None)

    with pytest.raises(ValueError, match="APP_DB_USER and APP_DB_PASS are required"):
        _ = settings.app_url


@pytest.mark.unit
def test_database_settings_builds_app_url(clean_database_env, monkeypatch):
    for k, v in _BASE_DB_ENV.items():
        monkeypatch.setenv(k, v)

    settings = DatabaseSettings(_env_file=None)

    assert (
        settings.app_url == "postgresql://app-user:app-pass@localhost:5432/testdb"
    )  # trufflehog:ignore


@pytest.mark.unit
def test_database_settings_admin_falls_back_to_app(clean_database_env, monkeypatch):
    for k, v in _BASE_DB_ENV.items():
        monkeypatch.setenv(k, v)

    settings = DatabaseSettings(_env_file=None)

    assert settings.admin_url == settings.app_url


@pytest.mark.unit
def test_database_settings_uses_admin_credentials_when_set(clean_database_env, monkeypatch):
    for k, v in _BASE_DB_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("ADMIN_DB_USER", "admin-user")
    monkeypatch.setenv("ADMIN_DB_PASS", "admin-pass")  # trufflehog:ignore

    settings = DatabaseSettings(_env_file=None)

    assert (
        settings.admin_url == "postgresql://admin-user:admin-pass@localhost:5432/testdb"
    )  # trufflehog:ignore
    assert (
        settings.app_url == "postgresql://app-user:app-pass@localhost:5432/testdb"
    )  # trufflehog:ignore


@pytest.mark.unit
def test_database_settings_raises_if_app_user_without_pass(clean_database_env, monkeypatch):
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("APP_DB_USER", "app-user")

    with pytest.raises(ValidationError, match="APP_DB_PASS"):
        DatabaseSettings(_env_file=None)


@pytest.mark.unit
def test_database_settings_admin_only_for_migration(clean_database_env, monkeypatch):
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("ADMIN_DB_USER", "admin-user")
    monkeypatch.setenv("ADMIN_DB_PASS", "admin-pass")  # trufflehog:ignore

    settings = DatabaseSettings(_env_file=None)

    assert (
        settings.admin_url == "postgresql://admin-user:admin-pass@localhost:5432/testdb"
    )  # trufflehog:ignore
    with pytest.raises(ValueError, match="APP_DB_USER"):
        _ = settings.app_url


@pytest.mark.unit
def test_database_settings_raises_if_admin_user_without_pass(clean_database_env, monkeypatch):
    for k, v in _BASE_DB_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("ADMIN_DB_USER", "admin-user")

    with pytest.raises(ValidationError, match="ADMIN_DB_PASS"):
        DatabaseSettings(_env_file=None)


@pytest.mark.unit
def test_database_settings_unix_socket_url(clean_database_env, monkeypatch):
    monkeypatch.setenv("DB_HOST", "/cloudsql/project:region:instance")
    monkeypatch.setenv("DB_NAME", "mydb")
    monkeypatch.setenv("APP_DB_USER", "app-user")
    monkeypatch.setenv("APP_DB_PASS", "app-pass")  # trufflehog:ignore

    settings = DatabaseSettings(_env_file=None)

    expected = (
        "postgresql://app-user:app-pass@/mydb"
        "?host=/cloudsql/project:region:instance"  # trufflehog:ignore
    )
    assert settings.app_url == expected


@pytest.mark.unit
def test_database_settings_url_encodes_special_chars(clean_database_env, monkeypatch):
    for k, v in _BASE_DB_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_DB_PASS", "p@ss:w/ord")  # trufflehog:ignore

    settings = DatabaseSettings(_env_file=None)

    assert "p%40ss%3Aw%2Ford" in settings.app_url


@pytest.mark.unit
def test_get_database_url_returns_app_url(clean_database_env, monkeypatch):
    for k, v in _BASE_DB_ENV.items():
        monkeypatch.setenv(k, v)
    settings = DatabaseSettings(_env_file=None)
    monkeypatch.setattr(database, "get_database_settings", lambda: settings)

    assert database.get_database_url() == settings.app_url


@pytest.mark.unit
def test_get_database_url_returns_configured_url(clean_database_env, monkeypatch):
    for k, v in _BASE_DB_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_NAME", "direct-db")
    monkeypatch.setenv("APP_DB_USER", "direct-user")
    monkeypatch.setenv("APP_DB_PASS", "direct-pass")  # trufflehog:ignore
    settings = DatabaseSettings(_env_file=None)
    monkeypatch.setattr(database, "get_database_settings", lambda: settings)

    assert (
        database.get_database_url()
        == "postgresql://direct-user:direct-pass@db.example.com:5432/direct-db"  # trufflehog:ignore
    )


@pytest.mark.unit
def test_database_url_comes_from_component_env_vars(clean_database_env, monkeypatch):
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test-db")
    monkeypatch.setenv("APP_DB_USER", "test-user")
    monkeypatch.setenv("APP_DB_PASS", "test-pass")  # trufflehog:ignore
    settings = DatabaseSettings(_env_file=None)
    monkeypatch.setattr(database, "get_database_settings", lambda: settings)

    assert (
        database.get_database_url()
        == "postgresql://test-user:test-pass@localhost:5432/test-db"  # trufflehog:ignore
    )


@pytest.mark.unit
def test_frontend_url_uses_dev_default(clean_frontend_env):
    settings = FrontendSettings(_env_file=None)

    assert settings.url == "http://localhost:3000"


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
def test_auth_settings_uses_defaults(clean_auth_env, monkeypatch):
    # SESSION_SECRET_KEY is required; provide it so the other defaults can be checked.
    monkeypatch.setenv("SESSION_SECRET_KEY", "session-secret-key")
    settings = AuthSettings(_env_file=None)

    assert settings.email_password_enabled is True
    assert settings.registration_enabled is True
    assert settings.google_client_id is None
    assert settings.google_client_secret is None
    assert settings.github_client_id is None
    assert settings.github_client_secret is None
    assert settings.session_secret_key == "session-secret-key"
    assert settings.jwt_secret_key is None
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_token_expire_minutes == 10080
    assert settings.google_enabled is False
    assert settings.github_enabled is False


@pytest.mark.unit
def test_auth_settings_requires_session_secret_key(clean_auth_env):
    with pytest.raises(ValidationError, match="SESSION_SECRET_KEY"):
        AuthSettings(_env_file=None)


@pytest.mark.unit
def test_auth_settings_loads_existing_environment_variables(clean_auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_EMAIL_PASSWORD_ENABLED", "false")
    monkeypatch.setenv("AUTH_REGISTRATION_ENABLED", "0")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setenv("GH_CLIENT_ID", "github-client-id")
    monkeypatch.setenv("GH_CLIENT_SECRET", "github-client-secret")
    monkeypatch.setenv("SESSION_SECRET_KEY", "session-secret-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS384")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")

    settings = AuthSettings(_env_file=None)

    assert settings.email_password_enabled is False
    assert settings.registration_enabled is False
    assert settings.google_client_id == "google-client-id"
    assert settings.google_client_secret == "google-client-secret"
    assert settings.github_client_id == "github-client-id"
    assert settings.github_client_secret == "github-client-secret"
    assert settings.session_secret_key == "session-secret-key"
    assert settings.jwt_secret_key == "jwt-secret-key"
    assert settings.jwt_algorithm == "HS384"
    assert settings.jwt_access_token_expire_minutes == 30
    assert settings.google_enabled is True
    assert settings.github_enabled is True


@pytest.mark.unit
def test_auth_settings_oauth_enabled_requires_client_id_and_secret(clean_auth_env, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET_KEY", "session-secret-key")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GH_CLIENT_SECRET", "github-client-secret")

    settings = AuthSettings(_env_file=None)

    assert settings.google_enabled is False
    assert settings.github_enabled is False


@pytest.mark.unit
def test_get_auth_settings_cache_clear_allows_env_overrides(clean_auth_env, monkeypatch):
    # SESSION_SECRET_KEY is required, so it must be set before AuthSettings loads.
    monkeypatch.setenv("SESSION_SECRET_KEY", "initial-session-secret-key")
    assert get_auth_settings().session_secret_key == "initial-session-secret-key"
    assert get_auth_settings().jwt_secret_key is None

    monkeypatch.setenv("SESSION_SECRET_KEY", "cached-session-secret-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "cached-jwt-secret-key")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "45")
    get_auth_settings.cache_clear()

    assert get_auth_settings().session_secret_key == "cached-session-secret-key"
    assert get_auth_settings().jwt_secret_key == "cached-jwt-secret-key"
    assert get_auth_settings().jwt_access_token_expire_minutes == 45


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
def test_storage_settings_uses_local_defaults(clean_storage_env):
    settings = StorageSettings(_env_file=None)

    assert settings.service_uri == "file:///app/storage"
    assert settings.service_account_key is None
    assert settings.local_storage_path == "/tmp/rhesis-files"


@pytest.mark.unit
def test_storage_settings_loads_existing_environment_variables(clean_storage_env, monkeypatch):
    monkeypatch.setenv("STORAGE_SERVICE_URI", "gs://rhesis-files")
    monkeypatch.setenv("STORAGE_SERVICE_ACCOUNT_KEY", "encoded-service-account")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", "/var/lib/rhesis-files")

    settings = StorageSettings(_env_file=None)

    assert settings.service_uri == "gs://rhesis-files"
    assert settings.service_account_key == "encoded-service-account"
    assert settings.local_storage_path == "/var/lib/rhesis-files"


@pytest.mark.unit
def test_get_storage_settings_cache_clear_allows_env_overrides(clean_storage_env, monkeypatch):
    assert get_storage_settings().service_uri == "file:///app/storage"

    monkeypatch.setenv("STORAGE_SERVICE_URI", "s3://rhesis-files")
    get_storage_settings.cache_clear()

    assert get_storage_settings().service_uri == "s3://rhesis-files"


@pytest.mark.unit
def test_smtp_settings_uses_defaults(clean_smtp_env):
    settings = SMTPSettings(_env_file=None)

    assert settings.host is None
    assert settings.port == 587
    assert settings.user is None
    assert settings.password is None
    assert settings.from_email == "engineering@rhesis.ai"


@pytest.mark.unit
def test_smtp_settings_loads_existing_environment_variables(clean_smtp_env, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("FROM_EMAIL", "noreply@example.com")

    settings = SMTPSettings(_env_file=None)

    assert settings.host == "smtp.example.com"
    assert settings.port == 465
    assert settings.user == "user@example.com"
    assert settings.password == "smtp-password"
    assert settings.from_email == "noreply@example.com"


@pytest.mark.unit
def test_get_smtp_settings_cache_clear_allows_env_overrides(clean_smtp_env, monkeypatch):
    assert get_smtp_settings().host is None

    monkeypatch.setenv("SMTP_HOST", "cached-smtp.example.com")
    get_smtp_settings.cache_clear()

    assert get_smtp_settings().host == "cached-smtp.example.com"


@pytest.mark.unit
def test_smtp_service_uses_settings_defaults(clean_smtp_env):
    service = SMTPService()

    assert service.smtp_host is None
    assert service.smtp_port == 587
    assert service.smtp_user is None
    assert service.smtp_password is None
    assert service.from_email == '"Harry from Rhesis AI" <engineering@rhesis.ai>'
    assert service.is_configured is False


@pytest.mark.unit
def test_smtp_service_uses_configured_settings(clean_smtp_env, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("FROM_EMAIL", '"Rhesis Notifications" <noreply@example.com>')
    get_smtp_settings.cache_clear()

    service = SMTPService()

    assert service.smtp_host == "smtp.example.com"
    assert service.smtp_port == 465
    assert service.smtp_user == "user@example.com"
    assert service.smtp_password == "smtp-password"
    assert service.from_email == '"Rhesis Notifications" <noreply@example.com>'
    assert service.is_configured is True


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
def test_application_settings_api_base_url_uses_dev_default(clean_application_env):
    settings = ApplicationSettings(_env_file=None)

    assert settings.api_base_url == "http://localhost:8080"


@pytest.mark.unit
def test_application_settings_defaults(minimal_application_env):
    """Optional fields use their declared defaults when only required vars are set."""
    settings = ApplicationSettings(_env_file=None)

    assert settings.quick_start is False
    assert settings.backend_env == "development"
    assert settings.gcp_project is None
    assert settings.google_cloud_project is None
    assert settings.cloud_run_service is None
    assert settings.cloud_run_revision is None
    assert settings.api_base_url == "https://api.example.com"
    # Default posture is non-production.
    assert settings.is_production is False
    assert settings.is_development is True


@pytest.mark.unit
def test_application_settings_loads_existing_environment_variables(
    clean_application_env, monkeypatch
):
    monkeypatch.setenv("QUICK_START", "true")
    monkeypatch.setenv("BACKEND_ENV", "Production")
    monkeypatch.setenv("GCP_PROJECT", "rhesis-prod")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "rhesis-prod-2")
    monkeypatch.setenv("K_SERVICE", "rhesis-backend")
    monkeypatch.setenv("K_REVISION", "rhesis-backend-00042-abc")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")

    settings = ApplicationSettings(_env_file=None)

    assert settings.quick_start is True
    assert settings.api_base_url == "https://api.example.com"
    assert settings.backend_env == "production"
    assert settings.gcp_project == "rhesis-prod"
    assert settings.google_cloud_project == "rhesis-prod-2"
    assert settings.cloud_run_service == "rhesis-backend"
    assert settings.cloud_run_revision == "rhesis-backend-00042-abc"


@pytest.mark.unit
@pytest.mark.parametrize(
    "backend_env,expected_is_production",
    [
        ("production", True),
        ("PRODUCTION", True),
        ("development", False),
        ("local", False),
        ("staging", False),
        ("", False),
    ],
)
def test_application_settings_is_production(
    minimal_application_env, monkeypatch, backend_env, expected_is_production
):
    """is_production is driven exclusively by BACKEND_ENV."""
    if backend_env:
        monkeypatch.setenv("BACKEND_ENV", backend_env)

    settings = ApplicationSettings(_env_file=None)

    assert settings.is_production is expected_is_production
    assert settings.is_development is (not expected_is_production)


@pytest.mark.unit
def test_get_application_settings_cache_clear_allows_env_overrides(
    minimal_application_env, monkeypatch
):
    assert get_application_settings().is_development is True

    monkeypatch.setenv("BACKEND_ENV", "production")
    get_application_settings.cache_clear()

    assert get_application_settings().is_development is False
    assert get_application_settings().backend_env == "production"


@pytest.mark.unit
def test_application_settings_api_base_url_validation(clean_application_env, monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "not-a-url")

    with pytest.raises(ValidationError):
        ApplicationSettings(_env_file=None)


@pytest.mark.unit
def test_get_application_settings_api_base_url_cache_clear(
    minimal_application_env, monkeypatch
):
    assert get_application_settings().api_base_url == "https://api.example.com"

    monkeypatch.setenv("API_BASE_URL", "https://cached-api.example.com")
    get_application_settings.cache_clear()

    assert get_application_settings().api_base_url == "https://cached-api.example.com"


@pytest.mark.unit
def test_rhesis_settings_uses_system_defaults(clean_rhesis_env):
    settings = RhesisSettings(_env_file=None)

    assert settings.base_url == "https://api.rhesis.ai"
    assert settings.api_key is None


@pytest.mark.unit
def test_rhesis_settings_loads_existing_environment_variables(clean_rhesis_env, monkeypatch):
    monkeypatch.setenv("RHESIS_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("RHESIS_API_KEY", "test-rhesis-api-key")

    settings = RhesisSettings(_env_file=None)

    assert settings.base_url == "https://api.example.com"
    assert settings.api_key == "test-rhesis-api-key"


@pytest.mark.unit
def test_get_rhesis_settings_cache_clear_allows_env_overrides(clean_rhesis_env, monkeypatch):
    assert get_rhesis_settings().base_url == "https://api.rhesis.ai"
    assert get_rhesis_settings().api_key is None

    monkeypatch.setenv("RHESIS_BASE_URL", "https://cached-api.example.com")
    monkeypatch.setenv("RHESIS_API_KEY", "cached-rhesis-api-key")
    get_rhesis_settings.cache_clear()

    assert get_rhesis_settings().base_url == "https://cached-api.example.com"
    assert get_rhesis_settings().api_key == "cached-rhesis-api-key"


@pytest.mark.unit
def test_telemetry_settings_uses_system_defaults(clean_telemetry_env):
    settings = TelemetrySettings(_env_file=None)

    assert settings.otlp_endpoint == "https://telemetry.rhesis.ai"
    assert settings.service_name == "rhesis"
    assert settings.deployment_type == "self-hosted"
    assert settings.rhesis_telemetry_enabled is True


@pytest.mark.unit
def test_telemetry_settings_loads_existing_environment_variables(
    clean_telemetry_env,
    monkeypatch,
):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otel.example.com")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "rhesis-worker")
    monkeypatch.setenv("OTEL_DEPLOYMENT_TYPE", "cloud")
    monkeypatch.setenv("OTEL_RHESIS_TELEMETRY_ENABLED", "false")

    settings = TelemetrySettings(_env_file=None)

    assert settings.otlp_endpoint == "https://otel.example.com"
    assert settings.service_name == "rhesis-worker"
    assert settings.deployment_type == "cloud"
    assert settings.rhesis_telemetry_enabled is False


@pytest.mark.unit
def test_get_telemetry_settings_cache_clear_allows_env_overrides(
    clean_telemetry_env,
    monkeypatch,
):
    assert get_telemetry_settings().service_name == "rhesis"

    monkeypatch.setenv("OTEL_SERVICE_NAME", "cached-rhesis")
    get_telemetry_settings.cache_clear()

    assert get_telemetry_settings().service_name == "cached-rhesis"

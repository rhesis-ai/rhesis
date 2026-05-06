import os

# =============================================================================
# Environment Setup - MUST be done BEFORE any backend imports
# =============================================================================
# Single source of truth for test environment variables.
# The CI workflow (backend-test.yml) only sets PYTHONPATH; everything else
# is configured here so there is no duplication to keep in sync.

# Port constants (must match tests/docker-compose.test.yml --profile backend)
DATABASE_PORT = 12001
REDIS_PORT = 12002

_TEST_DB_URL = (
    f"postgresql://rhesis-user:your-secured-password@localhost:{DATABASE_PORT}/rhesis-test-db"
)

_TEST_ENV_VARS = {
    "SQLALCHEMY_DB_MODE": "test",
    "ENVIRONMENT": "test",
    "LOG_LEVEL": "WARNING",
    "RHESIS_CONNECTOR_DISABLED": "true",
    "RHESIS_PROJECT_ID": "12340000-0000-4000-8000-000000001234",
    "SQLALCHEMY_DB_HOST": "localhost",
    "SQLALCHEMY_DB_PORT": str(DATABASE_PORT),
    "SQLALCHEMY_DB_NAME": "rhesis-test-db",
    "SQLALCHEMY_DB_USER": "rhesis-user",
    "SQLALCHEMY_DB_PASS": "your-secured-password",
    "SQLALCHEMY_DB_DRIVER": "postgresql",
    "SQLALCHEMY_DATABASE_TEST_URL": _TEST_DB_URL,
    "REDIS_URL": f"redis://:rhesis-redis-pass@localhost:{REDIS_PORT}/0",
    "BROKER_URL": f"redis://:rhesis-redis-pass@localhost:{REDIS_PORT}/0",
    "CELERY_RESULT_BACKEND": f"redis://:rhesis-redis-pass@localhost:{REDIS_PORT}/1",
    "JWT_SECRET_KEY": "test-jwt-secret-key-for-backend-tests",
    "SESSION_SECRET_KEY": "test-session-secret-key-for-backend-tests",
    "JWT_ALGORITHM": "HS256",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "10080",
    "DB_ENCRYPTION_KEY": "Zb21wZbPsUpb-c2JKj8uMugk767pWXHFTsjocd0Orac=",
    "SSO_ENCRYPTION_KEY": "9KgQ8O8Dx3xfUejfiAwkDgYMqD_2vekaNYw2WvqvJdw=",
    "AUTH0_DOMAIN": "test.auth0.com",
}


def _apply_test_env():
    """Apply (or re-apply) all test environment variables."""
    os.environ.update(_TEST_ENV_VARS)


_apply_test_env()

# =============================================================================
# Fixture imports — these trigger backend app loading which may call
# load_dotenv() and clobber our env vars.  We re-apply afterwards.
# =============================================================================

import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

# Import all modular fixtures
from tests.backend.fixtures import *  # noqa: E402, F403

# Import all entity fixtures to make them available to tests
from tests.backend.routes.fixtures.entities import *  # noqa: E402, F403

# Re-apply test env vars — the import chain above may have called
# load_dotenv(override=True) which overwrites our settings with .env values.
_apply_test_env()

# =============================================================================
# Session-scoped database migrations
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def run_migrations_once():
    """
    Run Alembic migrations once per test session.

    Idempotent: if the DB is already at head, this is a fast no-op.
    Set RHESIS_SKIP_MIGRATIONS=1 to skip (e.g. for unit-only runs without DB).
    """
    if os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        yield
        return

    backend_dir = (
        Path(__file__).parent.parent.parent / "apps" / "backend" / "src" / "rhesis" / "backend"
    )

    env = os.environ.copy()
    env["SQLALCHEMY_DB_MODE"] = "test"
    env["SQLALCHEMY_DATABASE_TEST_URL"] = _TEST_DB_URL
    env["DB_ENCRYPTION_KEY"] = _TEST_ENV_VARS["DB_ENCRYPTION_KEY"]

    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(
            f"Database migrations failed (returncode={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}\n"
            "Set RHESIS_SKIP_MIGRATIONS=1 to skip migrations for unit-only runs."
        )

    yield


# Simple fixtures for testing markers functionality


@pytest.fixture
def sample_prompt():
    return "Generate tests for a financial chatbot that helps with loans"


@pytest.fixture
def mock_test_data():
    return {
        "test_cases": [
            {"input": "What's my balance?", "expected": "account_inquiry"},
            {"input": "How do I apply for a loan?", "expected": "loan_application"},
        ]
    }


# All modular fixtures are now imported from tests.backend.fixtures


# ============================================================================
# Telemetry Testing Fixtures
# ============================================================================


@pytest.fixture
def disable_telemetry():
    """Fixture to disable telemetry for a test."""
    from rhesis.backend.telemetry.instrumentation import (
        _TELEMETRY_GLOBALLY_ENABLED,
        _set_telemetry_enabled_for_testing,
    )

    original_state = _TELEMETRY_GLOBALLY_ENABLED
    _set_telemetry_enabled_for_testing(False)
    yield
    _set_telemetry_enabled_for_testing(original_state)


@pytest.fixture
def enable_telemetry():
    """Fixture to enable telemetry for a test."""
    from rhesis.backend.telemetry.instrumentation import (
        _TELEMETRY_GLOBALLY_ENABLED,
        _set_telemetry_enabled_for_testing,
    )

    original_state = _TELEMETRY_GLOBALLY_ENABLED
    _set_telemetry_enabled_for_testing(True)
    yield
    _set_telemetry_enabled_for_testing(original_state)


@pytest.fixture
def telemetry_context():
    """Fixture to provide telemetry context management for testing."""
    from rhesis.backend.telemetry.instrumentation import (
        _TELEMETRY_GLOBALLY_ENABLED,
        _set_telemetry_enabled_for_testing,
    )

    class TelemetryContext:
        def __init__(self):
            self.original_state = _TELEMETRY_GLOBALLY_ENABLED

        def enable(self):
            _set_telemetry_enabled_for_testing(True)

        def disable(self):
            _set_telemetry_enabled_for_testing(False)

        def restore(self):
            _set_telemetry_enabled_for_testing(self.original_state)

    context = TelemetryContext()
    yield context
    context.restore()


@pytest.fixture(autouse=True)
def isolate_telemetry_context():
    """
    Auto-use fixture that ensures telemetry context variables are isolated per test.
    This prevents context leakage between tests.
    """
    from rhesis.backend.telemetry.instrumentation import (
        _telemetry_enabled,
        _telemetry_org_id,
        _telemetry_user_id,
    )

    _telemetry_enabled.set(False)
    _telemetry_user_id.set(None)
    _telemetry_org_id.set(None)

    yield

    _telemetry_enabled.set(False)
    _telemetry_user_id.set(None)
    _telemetry_org_id.set(None)


@pytest.fixture(autouse=True)
def disable_enrichment(request, monkeypatch):
    """
    Disable trace enrichment for all tests by default.

    Enrichment is expensive and tested separately in test_enrichment*.py files.
    This fixture makes enrichment a no-op for tests that don't explicitly need it.

    Tests in enrichment test modules are automatically excluded from this mock.
    """
    test_module = request.node.fspath.basename
    if "test_enrichment" in test_module:
        yield
        return

    def mock_enqueue_enrichment(
        self, trace_id, project_id, organization_id, workers_available=None, root_span_id=None
    ):
        return False

    monkeypatch.setattr(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService.enqueue_enrichment",
        mock_enqueue_enrichment,
    )

    yield

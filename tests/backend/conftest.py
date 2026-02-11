import os

# =============================================================================
# Environment Setup - MUST be done BEFORE any backend imports
# =============================================================================
# This mirrors the CI workflow (backend-test.yml) which sets env vars directly

# Test mode
os.environ["SQLALCHEMY_DB_MODE"] = "test"

# Disable the Rhesis connector/SDK integration for tests
os.environ["RHESIS_CONNECTOR_DISABLED"] = "true"
os.environ["RHESIS_PROJECT_ID"] = "12340000-0000-4000-8000-000000001234"

# Database configuration for docker-compose integration tests (port 12000)
# These are set directly (not setdefault) to override any .env file values
os.environ["SQLALCHEMY_DB_HOST"] = "localhost"
os.environ["SQLALCHEMY_DB_PORT"] = "12000"
os.environ["SQLALCHEMY_DB_NAME"] = "rhesis-test-db"
os.environ["SQLALCHEMY_DB_USER"] = "rhesis-user"
os.environ["SQLALCHEMY_DB_PASS"] = "your-secured-password"
os.environ["SQLALCHEMY_DB_DRIVER"] = "postgresql"
# Don't set SQLALCHEMY_DATABASE_URL - let the isolation check distinguish test from prod
os.environ["SQLALCHEMY_DATABASE_TEST_URL"] = (
    "postgresql://rhesis-user:your-secured-password@localhost:12000/rhesis-test-db"
)

# JWT configuration
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-backend-tests"
os.environ["JWT_ALGORITHM"] = "HS256"

# Encryption key
os.environ["DB_ENCRYPTION_KEY"] = "Zb21wZbPsUpb-c2JKj8uMugk767pWXHFTsjocd0Orac="

# Auth0 configuration (required for auth endpoints to not return 500)
os.environ["AUTH0_DOMAIN"] = "test.auth0.com"

# =============================================================================
# Database migrations (pytest fixture - runs before tests that need DB)
# =============================================================================

import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

# Import all modular fixtures
from tests.backend.fixtures import *  # noqa: E402, F403

# Import all entity fixtures to make them available to tests
from tests.backend.routes.fixtures.entities import *  # noqa: E402, F403

# =============================================================================
# Session-scoped database migrations
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def run_migrations_once():
    """
    Run Alembic migrations once per test session. Fails hard if migrations fail.

    Set RHESIS_SKIP_MIGRATIONS=1 to skip (e.g. for unit-only runs without DB).
    """
    if os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        yield
        return

    print("🔄 Running database migrations...")
    backend_dir = (
        Path(__file__).parent.parent.parent / "apps" / "backend" / "src" / "rhesis" / "backend"
    )

    env = os.environ.copy()
    env["SQLALCHEMY_DB_MODE"] = "test"
    env["SQLALCHEMY_DATABASE_TEST_URL"] = os.environ.get(
        "SQLALCHEMY_DATABASE_TEST_URL",
        "postgresql://rhesis-user:your-secured-password@localhost:12000/rhesis-test-db",
    )
    env["DB_ENCRYPTION_KEY"] = os.environ.get(
        "DB_ENCRYPTION_KEY", "Zb21wZbPsUpb-c2JKj8uMugk767pWXHFTsjocd0Orac="
    )

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

    print("✅ Migrations completed")
    yield


# Simple fixtures for testing markers functionality


@pytest.fixture
def sample_prompt():
    """🧠 Sample AI prompt for testing"""
    return "Generate tests for a financial chatbot that helps with loans"


@pytest.fixture
def mock_test_data():
    """📝 Mock test data structure"""
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
    """
    Fixture to disable telemetry for a test.

    Usage:
        def test_something(disable_telemetry):
            # Telemetry is disabled for this test
            ...
    """
    # Store original state
    from rhesis.backend.telemetry.instrumentation import (
        _TELEMETRY_GLOBALLY_ENABLED,
        _set_telemetry_enabled_for_testing,
    )

    original_state = _TELEMETRY_GLOBALLY_ENABLED

    # Disable telemetry for test
    _set_telemetry_enabled_for_testing(False)

    yield

    # Restore original state
    _set_telemetry_enabled_for_testing(original_state)


@pytest.fixture
def enable_telemetry():
    """
    Fixture to enable telemetry for a test.

    Usage:
        def test_telemetry_tracking(enable_telemetry):
            # Telemetry is enabled for this test
            ...
    """
    # Store original state
    from rhesis.backend.telemetry.instrumentation import (
        _TELEMETRY_GLOBALLY_ENABLED,
        _set_telemetry_enabled_for_testing,
    )

    original_state = _TELEMETRY_GLOBALLY_ENABLED

    # Enable telemetry for test
    _set_telemetry_enabled_for_testing(True)

    yield

    # Restore original state
    _set_telemetry_enabled_for_testing(original_state)


@pytest.fixture
def telemetry_context():
    """
    Fixture to provide telemetry context management for testing.

    Usage:
        def test_telemetry(telemetry_context):
            telemetry_context.enable()
            # Test with telemetry enabled

            telemetry_context.disable()
            # Test with telemetry disabled
    """
    from rhesis.backend.telemetry.instrumentation import (
        _TELEMETRY_GLOBALLY_ENABLED,
        _set_telemetry_enabled_for_testing,
    )

    class TelemetryContext:
        def __init__(self):
            self.original_state = _TELEMETRY_GLOBALLY_ENABLED

        def enable(self):
            """Enable telemetry for testing"""
            _set_telemetry_enabled_for_testing(True)

        def disable(self):
            """Disable telemetry for testing"""
            _set_telemetry_enabled_for_testing(False)

        def restore(self):
            """Restore original telemetry state"""
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

    # Reset context variables before each test
    _telemetry_enabled.set(False)
    _telemetry_user_id.set(None)
    _telemetry_org_id.set(None)

    yield

    # Clean up after test
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
    # Skip mocking if test is in an enrichment test module
    test_module = request.node.fspath.basename
    if "test_enrichment" in test_module:
        yield
        return

    # Mock enqueue_enrichment to return False (indicating sync fallback was used)
    # but don't actually do any enrichment work
    def mock_enqueue_enrichment(
        self, trace_id, project_id, organization_id, workers_available=None
    ):
        """Mock enqueue_enrichment to skip enrichment entirely."""
        return False  # Indicate we "used" sync fallback but actually do nothing

    # Patch the method on EnrichmentService to skip enrichment
    monkeypatch.setattr(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService.enqueue_enrichment",
        mock_enqueue_enrichment,
    )

    yield

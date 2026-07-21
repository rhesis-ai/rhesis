import os
import tempfile

# =============================================================================
# Environment Setup - MUST be done BEFORE any backend imports
# =============================================================================
# Single source of truth for test environment variables.
# The CI workflow (backend-test.yml) only sets PYTHONPATH; everything else
# is configured here so there is no duplication to keep in sync.

# Port constants (must match tests/docker-compose.test.yml --profile backend)
DATABASE_PORT = 12001
REDIS_PORT = 12002

_TEST_DB_USER = "rhesis-user"
_TEST_DB_PASS = "your-secured-password"  # trufflehog:ignore
_TEST_DB_HOST = "localhost"
_TEST_DB_PORT = str(DATABASE_PORT)
_TEST_DB_NAME = "rhesis-test-db"
_TEST_DB_DRIVER = "postgresql"

_TEST_ENV_VARS = {
    "LOG_LEVEL": "WARNING",
    "RHESIS_CONNECTOR_DISABLED": "true",
    "RHESIS_PROJECT_ID": "12340000-0000-4000-8000-000000001234",
    "FRONTEND_URL": "http://localhost:3000",
    "API_BASE_URL": "http://localhost:8080",
    "DB_DRIVER": _TEST_DB_DRIVER,
    "DB_HOST": _TEST_DB_HOST,
    "DB_PORT": _TEST_DB_PORT,
    "DB_NAME": _TEST_DB_NAME,
    "APP_DB_USER": _TEST_DB_USER,
    "APP_DB_PASS": _TEST_DB_PASS,
    "STORAGE_SERVICE_URI": f"file://{os.path.join(tempfile.gettempdir(), 'rhesis-test-storage')}",
    "BROKER_URL": f"redis://:rhesis-redis-pass@localhost:{REDIS_PORT}/0",
    "CELERY_RESULT_BACKEND": f"redis://:rhesis-redis-pass@localhost:{REDIS_PORT}/1",
    "JWT_SECRET_KEY": "test-jwt-secret-key-for-backend-tests",
    "SESSION_SECRET_KEY": "test-session-secret-key-for-backend-tests",
    "JWT_ALGORITHM": "HS256",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "10080",
    "DB_ENCRYPTION_KEY": "Zb21wZbPsUpb-c2JKj8uMugk767pWXHFTsjocd0Orac=",
    "SSO_ENCRYPTION_KEY": "9KgQ8O8Dx3xfUejfiAwkDgYMqD_2vekaNYw2WvqvJdw=",
    "OTEL_RHESIS_TELEMETRY_ENABLED": "false",
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


@pytest.fixture(autouse=True)
def isolate_storage_settings_cache():
    """Ensure tests that patch storage env vars do not reuse cached settings."""
    from importlib import import_module

    get_storage_settings = import_module(
        "rhesis.backend.app.config.settings"
    ).get_storage_settings
    get_storage_settings.cache_clear()
    yield
    get_storage_settings.cache_clear()


@pytest.fixture(autouse=True)
def _ensure_ee_features_registered():
    """Re-bootstrap EE features when the registry has been wiped.

    :class:`~rhesis.backend.app.features.FeatureRegistry` and
    :mod:`~rhesis.backend.app.auth.provider_hooks` are both process-global
    state, populated once by ``ee.bootstrap()`` at app import time — it never
    runs again during a test session. A unit test elsewhere that calls
    ``FeatureRegistry.reset()`` (for isolation) leaves the registry empty for
    the rest of the suite: every later test then sees RBAC as unregistered,
    ``PermissionAuthorizationProvider._rbac_available()`` returns False, and
    every RBAC permission check silently falls back to the community
    provider, denying broadly (explorer, behavior, endpoint, etc.).

    Cheap: dict inserts plus ``app.include_router`` on a mock. The enricher
    list is reset first so re-running ``bootstrap`` does not leave stale
    callbacks behind from a previous run. Autouse + suite-wide (not just
    ``tests/backend/ee/``) since the wipe can be triggered by tests anywhere
    (e.g. ``tests/backend/app/test_feature_registry.py``,
    ``tests/backend/routes/test_features.py``) and affects tests anywhere.
    """
    from rhesis.backend.app.features import FeatureRegistry

    if not FeatureRegistry._features:
        from unittest.mock import MagicMock

        from rhesis.backend.app.auth.provider_hooks import reset_enrichers
        from rhesis.backend.ee import bootstrap

        reset_enrichers()
        bootstrap(MagicMock())

    # Restore the EE authorization provider too. test_rbac.py and
    # test_permission_cache.py call _AuthorizationRegistry.reset() in teardown,
    # which swaps the active provider back to the permissive community
    # DefaultAuthorizationProvider. That reset does NOT clear _features, so the
    # branch above won't catch it — reinstall the EE provider directly so RBAC
    # is actually enforced for the next test. This runs before a test's own
    # setup_method, so provider-swapping tests that reset in their own setup
    # still take precedence for their duration.
    try:
        from rhesis.backend.app.auth.rbac import (
            get_authorization_provider,
            set_authorization_provider,
        )
        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider
    except ImportError:
        pass  # community build — no EE provider to restore
    else:
        if not isinstance(get_authorization_provider(), PermissionAuthorizationProvider):
            set_authorization_provider(PermissionAuthorizationProvider())

    # Restore the capability catalog if empty. auth/test_rbac.py and
    # test_object_level_auth.py call reset_capabilities() in teardown, leaving
    # _capability_cache = None; get_all_capabilities() then returns []. A
    # built-in role's permission set is computed as set(catalog), so an empty
    # catalog gives even Owner *zero* permissions — 403 on everything. Existing
    # re-register guards live only in security/, ee/rbac/, and
    # test_capabilities.py; restore it suite-wide here so routes/ tests (which
    # authorize against the shared Owner user) aren't denied wholesale.
    from rhesis.backend.app.auth.capabilities import get_all_capabilities, register_capabilities

    if not get_all_capabilities():
        from rhesis.backend.app.main import app

        register_capabilities(app)
    yield


@pytest.fixture(autouse=True)
def _ensure_session_user_is_owner(_ensure_ee_features_registered):
    """Guarantee the shared session-auth user holds the built-in Owner role.

    With RBAC enforced (see _ensure_ee_features_registered), every
    authenticated request from the shared test user is authorized against its
    ``organization_member`` role. The role must reliably be **Owner** — the
    creation flow seeds it as Member and the one-time promotion is fragile
    across the heavy load_initial_data path — so re-assert it here, per test,
    on a dedicated committed connection that the auth middleware's fresh
    get_db() will see. Idempotent and cheap (two indexed lookups when already
    correct). No-op in community builds or before session auth is created.

    Depends on _ensure_ee_features_registered so RBAC is registered first.
    """
    from tests.backend.fixtures import auth as _auth

    cache = _auth._session_auth_cache
    if cache is not None:
        import uuid as _uuid

        from tests.backend.fixtures.database import TestingSessionLocal
        from tests.backend.fixtures.test_setup import ensure_owner_membership

        org_id, user_id, _token = cache
        db = TestingSessionLocal()
        try:
            ensure_owner_membership(db, _uuid.UUID(org_id), _uuid.UUID(user_id))
            db.commit()
        except Exception as exc:  # never fail a test on the safety net itself
            db.rollback()
            print(f"⚠️ could not ensure session user Owner role: {exc}")
        finally:
            db.close()
    yield


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
    env["DB_DRIVER"] = _TEST_DB_DRIVER
    env["DB_HOST"] = _TEST_DB_HOST
    env["DB_PORT"] = _TEST_DB_PORT
    env["DB_NAME"] = _TEST_DB_NAME
    env["APP_DB_USER"] = _TEST_DB_USER
    env["APP_DB_PASS"] = _TEST_DB_PASS
    env["DB_ENCRYPTION_KEY"] = _TEST_ENV_VARS["DB_ENCRYPTION_KEY"]

    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "heads"],
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
def isolate_request_scope():
    """
    Per-test isolation of the RequestScope and tenant-filter-bypass ContextVars.

    Ensures no scope leaks between tests. Mirrors isolate_telemetry_context above.

    IMPORTANT: This fixture resets scope to the *unbound* default (all None).
    The auto-filter listener is a no-op when scope is unbound, so existing tests
    that pass explicit organization_id parameters to CRUD functions are unaffected.
    Do NOT bind scope from test_db; use the bound_scope helper fixture instead.
    """
    from rhesis.backend.app.scope import RequestScope, _scope, _tenant_filter_disabled

    scope_token = _scope.set(RequestScope())  # all-None default
    bypass_token = _tenant_filter_disabled.set(False)
    try:
        yield
    finally:
        _scope.reset(scope_token)
        _tenant_filter_disabled.reset(bypass_token)


@pytest.fixture
def bound_scope():
    """
    Helper fixture for tests that want to exercise the auto-filter/auto-stamp listeners.

    Usage:
        def test_something(test_db, bound_scope):
            with bound_scope(organization_id="...", user_id="..."):
                results = test_db.query(SomeModel).all()  # scope-filtered
    """
    from contextlib import contextmanager

    from rhesis.backend.app.scope import RequestScope, _scope

    @contextmanager
    def _bind(organization_id=None, user_id=None, project_id=None):
        token = _scope.set(RequestScope(organization_id=organization_id, user_id=user_id, project_id=project_id))
        try:
            yield
        finally:
            _scope.reset(token)

    return _bind


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

    def mock_enqueue_enrichment(self, trace_id, project_id, organization_id, root_span_id=None):
        return False

    monkeypatch.setattr(
        "rhesis.backend.app.services.telemetry.enrichment.EnrichmentService.enqueue_enrichment",
        mock_enqueue_enrichment,
    )

    yield

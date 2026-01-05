import os

import pytest
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables from test directory first, then backend
load_dotenv()  # Try current directory first
load_dotenv("tests/.env")  # Load from test directory where RHESIS_API_KEY should be
load_dotenv("apps/backend/.env")  # Then backend directory for other vars

# Set test mode environment variable BEFORE importing any backend modules
os.environ["SQLALCHEMY_DB_MODE"] = "test"

# Set up encryption key for tests if not already set
# This ensures tests can run even if no encryption key is configured in .env files
if "DB_ENCRYPTION_KEY" not in os.environ or not os.environ.get("DB_ENCRYPTION_KEY"):
    # Generate a test-specific encryption key that won't conflict with production
    test_encryption_key = Fernet.generate_key().decode()
    os.environ["DB_ENCRYPTION_KEY"] = test_encryption_key
    print("🔐 Generated test encryption key for test session")

# Import all modular fixtures
from tests.backend.fixtures import *

# Import all entity fixtures to make them available to tests
from tests.backend.routes.fixtures.entities import *

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
def disable_enrichment(monkeypatch):
    """
    Disable trace enrichment for all tests by default.
    
    Enrichment is expensive and tested separately in test_enrichment.py.
    This fixture makes enrichment a no-op for tests that don't explicitly need it.
    """
    # Mock enqueue_enrichment to return False (indicating sync fallback was used)
    # but don't actually do any enrichment work
    def mock_enqueue_enrichment(self, trace_id, project_id, organization_id, workers_available=None):
        """Mock enqueue_enrichment to skip enrichment entirely."""
        return False  # Indicate we "used" sync fallback but actually do nothing
    
    # Patch the method on EnrichmentService to skip enrichment
    monkeypatch.setattr(
        "rhesis.backend.app.services.telemetry.enrichment_service.EnrichmentService.enqueue_enrichment",
        mock_enqueue_enrichment,
    )

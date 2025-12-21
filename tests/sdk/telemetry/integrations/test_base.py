"""Tests for BaseIntegration class."""

from rhesis.sdk.telemetry.integrations.base import BaseIntegration


class MockIntegration(BaseIntegration):
    """Mock integration for testing."""

    def __init__(self, installed: bool = True):
        super().__init__()
        self._installed = installed
        self._callback_created = False

    @property
    def framework_name(self) -> str:
        return "mock_framework"

    def is_installed(self) -> bool:
        return self._installed

    def _create_callback(self):
        self._callback_created = True
        return "mock_callback"


def test_integration_not_installed():
    """Test integration when framework is not installed."""
    integration = MockIntegration(installed=False)

    result = integration.enable()

    assert result is False
    assert integration.enabled is False
    assert integration._callback is None


def test_integration_installed():
    """Test integration when framework is installed."""
    integration = MockIntegration(installed=True)

    result = integration.enable()

    assert result is True
    assert integration.enabled is True
    assert integration._callback == "mock_callback"
    assert integration._callback_created is True


def test_integration_enable_twice():
    """Test enabling integration twice."""
    integration = MockIntegration(installed=True)

    result1 = integration.enable()
    result2 = integration.enable()

    assert result1 is True
    assert result2 is True
    assert integration.enabled is True


def test_integration_disable():
    """Test disabling integration."""
    integration = MockIntegration(installed=True)

    integration.enable()
    assert integration.enabled is True

    integration.disable()
    assert integration.enabled is False
    assert integration._callback is None


def test_integration_callback():
    """Test getting callback handler."""
    integration = MockIntegration(installed=True)

    # Callback should auto-enable if not enabled
    callback = integration.callback()

    assert integration.enabled is True
    assert callback == "mock_callback"

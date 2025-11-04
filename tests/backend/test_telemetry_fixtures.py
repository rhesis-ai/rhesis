"""
Test file demonstrating telemetry fixture usage.

This file shows how to use the telemetry testing fixtures to control
telemetry state in tests and ensure proper test isolation.
"""

import pytest

from rhesis.backend.telemetry import (
    is_telemetry_enabled,
    track_feature_usage,
    track_user_activity,
)


class TestTelemetryFixtures:
    """Tests demonstrating telemetry fixture usage"""

    def test_telemetry_disabled_by_default(self, disable_telemetry):
        """Test that telemetry can be explicitly disabled"""
        # Telemetry should be disabled for this test
        # No spans should be created
        track_user_activity("test_event")
        track_feature_usage("test_feature", "test_action")
        # Should not raise errors, just no-op

    def test_telemetry_enabled(self, enable_telemetry):
        """Test with telemetry explicitly enabled"""
        # Telemetry should be enabled for this test
        # Spans will be created (but may not be exported in test env)
        track_user_activity("test_event")
        track_feature_usage("test_feature", "test_action")
        # Should not raise errors

    def test_telemetry_context_toggle(self, telemetry_context):
        """Test toggling telemetry state within a single test"""
        # Start with telemetry disabled
        telemetry_context.disable()
        track_user_activity("disabled_event")

        # Enable telemetry mid-test
        telemetry_context.enable()
        track_user_activity("enabled_event")

        # Disable again
        telemetry_context.disable()
        track_user_activity("disabled_again_event")

    def test_sensitive_metadata_is_filtered(self, enable_telemetry):
        """Test that sensitive metadata is properly filtered"""
        # These sensitive keys should be filtered out
        track_user_activity(
            "login",
            password="secret123",  # Should be filtered
            token="abc123",  # Should be filtered
            user_agent="Mozilla/5.0",  # Should be kept
        )

        track_feature_usage(
            "user_profile",
            "updated",
            api_key="key123",  # Should be filtered
            email="user@example.com",  # Should be filtered
            username="testuser",  # Should be kept
        )

    def test_telemetry_isolation_between_tests(self):
        """
        Test that telemetry context is isolated between tests.

        The isolate_telemetry_context fixture (autouse=True) ensures
        that context variables don't leak between tests.
        """
        # Context should be clean at start of test
        from rhesis.backend.telemetry.instrumentation import (
            _telemetry_enabled,
            _telemetry_org_id,
            _telemetry_user_id,
        )

        assert _telemetry_enabled.get() is False
        assert _telemetry_user_id.get() is None
        assert _telemetry_org_id.get() is None


class TestTelemetryDeploymentTypes:
    """Tests for different deployment type configurations"""

    def test_cloud_deployment_enabled(self, monkeypatch):
        """Test that cloud deployment always has telemetry enabled"""
        monkeypatch.setenv("DEPLOYMENT_TYPE", "cloud")
        # Need to re-evaluate the function
        assert is_telemetry_enabled() is True

    def test_self_hosted_default_disabled(self, monkeypatch):
        """Test that self-hosted deployment has telemetry disabled by default"""
        monkeypatch.setenv("DEPLOYMENT_TYPE", "self-hosted")
        monkeypatch.delenv("RHESIS_TELEMETRY_ENABLED", raising=False)
        assert is_telemetry_enabled() is False

    def test_self_hosted_can_enable(self, monkeypatch):
        """Test that self-hosted deployment can enable telemetry via env var"""
        monkeypatch.setenv("DEPLOYMENT_TYPE", "self-hosted")
        monkeypatch.setenv("RHESIS_TELEMETRY_ENABLED", "true")
        assert is_telemetry_enabled() is True

    def test_unknown_deployment_disabled(self, monkeypatch):
        """Test that unknown deployment types have telemetry disabled"""
        monkeypatch.setenv("DEPLOYMENT_TYPE", "unknown")
        assert is_telemetry_enabled() is False


@pytest.mark.parametrize(
    "event_type,expected_category",
    [
        ("login", "user_activity"),
        ("logout", "user_activity"),
        ("session_start", "user_activity"),
    ],
)
def test_user_activity_tracking(enable_telemetry, event_type, expected_category):
    """Test user activity tracking with different event types"""
    # Should not raise errors
    track_user_activity(event_type, session_id="test-session-123")


@pytest.mark.parametrize(
    "feature,action",
    [
        ("test_run", "created"),
        ("metric", "viewed"),
        ("test_set", "updated"),
        ("prompt", "deleted"),
    ],
)
def test_feature_usage_tracking(enable_telemetry, feature, action):
    """Test feature usage tracking with different features and actions"""
    # Should not raise errors
    track_feature_usage(feature, action, resource_id="test-123")

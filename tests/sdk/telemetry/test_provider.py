"""Tests for telemetry TracerProvider."""

from unittest.mock import patch

from opentelemetry.sdk.trace import TracerProvider

from rhesis.sdk.telemetry.provider import get_tracer_provider, shutdown_tracer_provider


class TestTracerProvider:
    """Tests for TracerProvider initialization."""

    def teardown_method(self):
        """Clean up after each test."""
        shutdown_tracer_provider()

    @patch("rhesis.sdk.telemetry.provider.RhesisOTLPExporter")
    def test_get_tracer_provider_creates_provider(self, mock_exporter):
        """Test get_tracer_provider creates a TracerProvider."""
        provider = get_tracer_provider(
            service_name="test-service",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        assert isinstance(provider, TracerProvider)
        assert provider is not None

    @patch("rhesis.sdk.telemetry.provider.RhesisOTLPExporter")
    def test_get_tracer_provider_singleton(self, mock_exporter):
        """Test get_tracer_provider returns same instance."""
        provider1 = get_tracer_provider(
            service_name="test-service",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        provider2 = get_tracer_provider(
            service_name="test-service",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        assert provider1 is provider2

    @patch("rhesis.sdk.telemetry.provider.RhesisOTLPExporter")
    def test_get_tracer_provider_initializes_exporter(self, mock_exporter):
        """Test get_tracer_provider creates exporter with correct params."""
        get_tracer_provider(
            service_name="test-service",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="production",
        )

        mock_exporter.assert_called_once_with(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="production",
        )

    @patch("rhesis.sdk.telemetry.provider.RhesisOTLPExporter")
    def test_get_tracer_provider_adds_batch_processor(self, mock_exporter):
        """Test get_tracer_provider adds batch span processor."""
        provider = get_tracer_provider(
            service_name="test-service",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        # Check that processor was added
        assert len(provider._active_span_processor._span_processors) > 0

    @patch("rhesis.sdk.telemetry.provider.RhesisOTLPExporter")
    def test_shutdown_tracer_provider(self, mock_exporter):
        """Test shutdown_tracer_provider clears singleton."""
        provider1 = get_tracer_provider(
            service_name="test-service",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        shutdown_tracer_provider()

        # After shutdown, getting provider again should create new instance
        provider2 = get_tracer_provider(
            service_name="test-service",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        assert provider1 is not provider2

    @patch("rhesis.sdk.telemetry.provider.RhesisOTLPExporter")
    def test_get_tracer_provider_creates_resource(self, mock_exporter):
        """Test get_tracer_provider creates resource with correct attributes."""
        provider = get_tracer_provider(
            service_name="my-service",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="staging",
        )

        resource = provider.resource
        assert resource.attributes["service.name"] == "my-service"
        assert resource.attributes["service.namespace"] == "rhesis"
        assert resource.attributes["deployment.environment"] == "staging"

"""Tests for REST endpoint invoker with test execution context."""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.services.invokers.rest_invoker import RestEndpointInvoker


class TestRestInvokerTestContext:
    """Test REST invoker with test execution context propagation."""

    def test_automatic_tracing_property(self):
        """Test that RestEndpointInvoker has automatic_tracing set to False."""
        invoker = RestEndpointInvoker()

        assert hasattr(invoker, "automatic_tracing")
        assert invoker.automatic_tracing is False

    @pytest.mark.asyncio
    async def test_invoke_accepts_test_execution_context(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test that invoke method accepts test_execution_context parameter."""
        invoker = RestEndpointInvoker()

        test_execution_context = {
            "test_run_id": str(uuid4()),
            "test_result_id": str(uuid4()),
            "test_id": str(uuid4()),
            "test_configuration_id": str(uuid4()),
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {"text": "Success"},
        }

        with patch("requests.post", return_value=mock_response):
            # Should not raise error when test_execution_context is provided
            result = await invoker.invoke(
                mock_db,
                sample_endpoint_rest,
                sample_input_data,
                test_execution_context=test_execution_context,
            )

        assert result["output"] == "Success"

    @pytest.mark.asyncio
    async def test_invoke_works_without_test_execution_context(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test that invoke works when test_execution_context is None or omitted."""
        invoker = RestEndpointInvoker()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {"text": "Success"},
        }

        with patch("requests.post", return_value=mock_response):
            # Test with None
            result = await invoker.invoke(
                mock_db,
                sample_endpoint_rest,
                sample_input_data,
                test_execution_context=None,
            )
            assert result["output"] == "Success"

            # Test without the parameter (backward compatibility)
            result = await invoker.invoke(
                mock_db,
                sample_endpoint_rest,
                sample_input_data,
            )
            assert result["output"] == "Success"

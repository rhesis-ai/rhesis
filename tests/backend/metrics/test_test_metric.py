"""
Simple test for run_metric_test function to verify it works with real database connections.
"""

import importlib.util

# Import the function we want to test from the backend using importlib to avoid pytest collection issues
import os
from unittest.mock import patch

# Load the backend module dynamically to avoid pytest collecting it as a test
backend_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "apps",
    "backend",
    "src",
    "rhesis",
    "backend",
    "metrics",
    "test_metric.py",
)
spec = importlib.util.spec_from_file_location("backend_test_metric", backend_path)
backend_test_metric = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_test_metric)

# Get the function we want to test
run_metric_test = backend_test_metric.run_metric_test


class TestMetricTestSimple:
    """Simple tests for run_metric_test function with updated session management"""

    def test_run_metric_test_basic(self):
        """Test that run_metric_test can be called without errors (new session management)"""
        # Mock only the database query functions to avoid real database dependencies
        with patch.object(backend_test_metric, "load_metric_from_db") as mock_load_metric:
            # Return None to trigger the "metric not found" path
            mock_load_metric.return_value = None

            # Call the function - now uses direct parameter passing instead of set_tenant
            result = run_metric_test(
                metric_id="nonexistent-metric",
                organization_id="test-org-456",
                user_id="test-user-789",
                input_text="Test input",
            )

            # Verify the function was called with the metric_id and organization_id
            mock_load_metric.assert_called_once()
            call_args = mock_load_metric.call_args
            # load_metric_from_db now takes (db_session, metric_id, organization_id)
            assert call_args[0][1] == "nonexistent-metric"  # metric_id
            assert call_args[0][2] == "test-org-456"  # organization_id (SECURITY)

            # Should get an error result since metric doesn't exist
            assert isinstance(result, dict)
            assert "error" in result

    def test_run_metric_test_with_error_handling(self):
        """Test that run_metric_test handles errors gracefully (new session management)"""
        # Test with invalid metric_id to trigger error handling
        # This test now benefits from organization filtering preventing data leakage
        result = run_metric_test(
            metric_id="nonexistent-metric",
            organization_id="test-org-456",
            user_id="test-user-789",
            input_text="Test input",
        )

        # Should get an error result
        assert isinstance(result, dict)
        assert "error" in result

    def test_run_metric_test_organization_isolation(self):
        """Test that organization filtering is enforced to prevent data leakage"""
        with patch.object(backend_test_metric, "load_metric_from_db") as mock_load_metric:
            # Return None to simulate metric not found in organization
            mock_load_metric.return_value = None

            result = run_metric_test(
                metric_id="some-metric",
                organization_id="org-123",
                user_id="user-456",
                input_text="Test input",
            )

            # SECURITY: Verify organization_id is passed to prevent cross-org data access
            mock_load_metric.assert_called_once()
            call_args = mock_load_metric.call_args
            # load_metric_from_db now takes (db_session, metric_id, organization_id)
            assert call_args[0][1] == "some-metric"  # metric_id
            assert call_args[0][2] == "org-123"  # organization_id (SECURITY CRITICAL)

            # Should get error since metric not found in this organization
            assert isinstance(result, dict)
            assert "error" in result

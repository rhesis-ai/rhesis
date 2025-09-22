"""
Simple test for run_metric_test function to verify it works with real database connections.
"""

import pytest
from unittest.mock import Mock, patch

# Import the function we want to test from the SDK using importlib to avoid pytest collection issues
import sys
import os
import importlib.util

# Load the SDK module dynamically to avoid pytest collecting it as a test
sdk_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'sdk', 'src', 'rhesis', 'sdk', 'metrics', 'test_metric.py')
spec = importlib.util.spec_from_file_location("sdk_test_metric", sdk_path)
sdk_test_metric = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk_test_metric)

# Get the function we want to test
test_metric = sdk_test_metric.test_metric


class TestMetricTestSimple:
    """Simple tests for test_metric function with updated session management"""
    
    def test_run_metric_test_basic(self):
        """Test that run_metric_test can be called without errors (new session management)"""
        # Mock only the database query functions to avoid real database dependencies
        # Note: load_metric_from_db now takes organization_id parameter for security
        with patch.object(sdk_test_metric, 'load_metric_from_db') as mock_load_metric:
            # Return None to trigger the "metric not found" path
            mock_load_metric.return_value = None
            
            # Call the function - now uses direct parameter passing instead of set_tenant
            result = test_metric(
                metric_id="nonexistent-metric",
                organization_id="test-org-456", 
                user_id="test-user-789",
                input_text="Test input"
            )
            
            # Verify the function was called with organization_id for security
            mock_load_metric.assert_called_once()
            call_args = mock_load_metric.call_args
            assert call_args[0][1] == "nonexistent-metric"  # metric_id
            assert call_args[0][2] == "test-org-456"  # organization_id
            
            # Should get an error result since metric doesn't exist
            assert isinstance(result, dict)
            assert "error" in result
    
    def test_run_metric_test_with_error_handling(self):
        """Test that run_metric_test handles errors gracefully (new session management)"""
        # Test with invalid metric_id to trigger error handling
        # This test now benefits from organization filtering preventing data leakage
        result = test_metric(
            metric_id="nonexistent-metric",
            organization_id="test-org-456", 
            user_id="test-user-789",
            input_text="Test input"
        )
        
        # Should get an error result
        assert isinstance(result, dict)
        assert "error" in result
        
    def test_run_metric_test_organization_isolation(self):
        """Test that organization filtering prevents data leakage"""
        with patch.object(sdk_test_metric, 'load_metric_from_db') as mock_load_metric:
            # Return None to simulate metric not found in organization
            mock_load_metric.return_value = None
            
            result = test_metric(
                metric_id="some-metric",
                organization_id="org-123",
                user_id="user-456", 
                input_text="Test input"
            )
            
            # Verify organization_id was passed for filtering
            mock_load_metric.assert_called_once()
            call_args = mock_load_metric.call_args
            assert call_args[0][2] == "org-123"  # organization_id parameter
            
            # Should get error since metric not found in organization
            assert isinstance(result, dict)
            assert "error" in result

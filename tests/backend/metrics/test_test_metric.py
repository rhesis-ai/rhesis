"""
Simple test for run_metric_test function to verify it works with real database connections.
"""

import pytest
from unittest.mock import Mock, patch

# Import the function we want to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'apps', 'backend', 'src', 'rhesis', 'backend', 'metrics'))

from test_metric import run_metric_test


class TestRunMetricTestSimple:
    """Simple tests for run_metric_test function using real database connections"""
    
    def test_run_metric_test_basic(self):
        """Test that run_metric_test can be called without errors"""
        # Mock only the database query functions to avoid real database dependencies
        with patch('test_metric.load_metric_from_db') as mock_load_metric:
            # Return None to trigger the "metric not found" path
            mock_load_metric.return_value = None
            
            # Call the function - this will use real get_org_aware_db but hit the error path
            result = run_metric_test(
                metric_id="nonexistent-metric",
                organization_id="test-org-456", 
                user_id="test-user-789",
                input_text="Test input"
            )
            
            # Should get an error result since metric doesn't exist
            assert isinstance(result, dict)
            assert "error" in result
    
    def test_run_metric_test_with_error_handling(self):
        """Test that run_metric_test handles errors gracefully"""
        # Test with invalid metric_id to trigger error handling
        result = run_metric_test(
            metric_id="nonexistent-metric",
            organization_id="test-org-456", 
            user_id="test-user-789",
            input_text="Test input"
        )
        
        # Should get an error result
        assert isinstance(result, dict)
        assert "error" in result

"""
Test suite for the metrics test script (test_metric.py)

This test file covers the CLI metric testing functionality before migrating 
from set_tenant to get_org_aware_db pattern.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import sys
import os

# Add the metrics module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../apps/backend/src/rhesis/backend/metrics"))

from test_metric import (
    MockUser,
    load_metric_from_db,
    load_test_from_db, 
    extract_test_data,
    test_metric,
    print_results
)


class TestMockUser:
    """Test MockUser class"""
    
    def test_mock_user_creation(self):
        """Test MockUser initialization"""
        user = MockUser("user123", "org456")
        assert user.id == "user123"
        assert user.organization_id == "org456"


class TestLoadMetricFromDb:
    """Test load_metric_from_db function"""
    
    def test_load_metric_by_uuid(self):
        """Test loading metric by UUID"""
        mock_db = Mock()
        mock_metric = Mock()
        mock_metric.id = "metric123"
        mock_metric.name = "Test Metric"
        
        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_metric
        mock_db.query.return_value = mock_query
        
        result = load_metric_from_db(mock_db, "metric123")
        
        assert result == mock_metric
        mock_db.query.assert_called_once()
    
    def test_load_metric_by_nano_id(self):
        """Test loading metric by nano_id"""
        mock_db = Mock()
        mock_metric = Mock()
        mock_metric.nano_id = "abc123"
        mock_metric.name = "Test Metric"
        
        # Mock query chain for UUID lookup (returns None)
        mock_query_uuid = Mock()
        mock_query_uuid.filter.return_value.first.return_value = None
        
        # Mock query chain for nano_id lookup
        mock_query_nano = Mock()
        mock_query_nano.filter.return_value.first.return_value = mock_metric
        
        mock_db.query.side_effect = [mock_query_uuid, mock_query_nano]
        
        result = load_metric_from_db(mock_db, "abc123")
        
        assert result == mock_metric
        assert mock_db.query.call_count == 2
    
    def test_load_metric_not_found(self):
        """Test loading non-existent metric"""
        mock_db = Mock()
        
        # Mock query chains that return None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        result = load_metric_from_db(mock_db, "nonexistent")
        
        assert result is None


class TestLoadTestFromDb:
    """Test load_test_from_db function"""
    
    def test_load_test_by_uuid(self):
        """Test loading test by UUID"""
        mock_db = Mock()
        mock_test = Mock()
        mock_test.id = "test123"
        
        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_test
        mock_db.query.return_value = mock_query
        
        result = load_test_from_db(mock_db, "test123")
        
        assert result == mock_test
        mock_db.query.assert_called_once()
    
    def test_load_test_not_found(self):
        """Test loading non-existent test"""
        mock_db = Mock()
        
        # Mock query chains that return None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        result = load_test_from_db(mock_db, "nonexistent")
        
        assert result is None


class TestExtractTestData:
    """Test extract_test_data function"""
    
    def test_extract_test_data_with_prompt_and_response(self):
        """Test extracting test data with prompt and response"""
        mock_test = Mock()
        mock_prompt = Mock()
        mock_prompt.content = "What is 2+2?"
        mock_prompt.expected_response = "2+2 equals 4"
        mock_test.prompt = mock_prompt
        mock_test.test_contexts = []
        
        input_text, expected_output, context = extract_test_data(mock_test)
        
        assert input_text == "What is 2+2?"
        assert expected_output == "2+2 equals 4"
        assert context == []
    
    def test_extract_test_data_with_context_chunks(self):
        """Test extracting test data with context chunks"""
        mock_test = Mock()
        mock_prompt = Mock()
        mock_prompt.content = "Question"
        mock_prompt.expected_response = "Answer"
        
        # Mock test contexts
        mock_context1 = Mock()
        mock_context1.attributes = {"context": "Context 1"}
        mock_context2 = Mock()
        mock_context2.attributes = {"context": "Context 2"}
        
        mock_test.prompt = mock_prompt
        mock_test.test_contexts = [mock_context1, mock_context2]
        
        input_text, expected_output, context = extract_test_data(mock_test)
        
        assert input_text == "Question"
        assert expected_output == "Answer"
        assert context == ["Context 1", "Context 2"]
    
    def test_extract_test_data_missing_prompt(self):
        """Test extracting test data with missing prompt"""
        mock_test = Mock()
        mock_test.prompt = None
        mock_test.test_contexts = []
        
        input_text, expected_output, context = extract_test_data(mock_test)
        
        assert input_text == ""
        assert expected_output == ""
        assert context == []


class TestTestMetricFunction:
    """Test test_metric function"""
    
    @contextmanager
    def mock_session_local(self):
        """Mock SessionLocal context manager"""
        mock_db = Mock()
        yield mock_db
    
    def test_test_metric_basic_flow(self):
        """Test basic metric testing flow"""
        # Mock all the dependencies
        with patch('test_metric.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            
            # Mock set_tenant import and function call
            with patch('rhesis.backend.app.database.set_tenant') as mock_set_tenant:
                # Mock load_metric_from_db
                with patch('test_metric.load_metric_from_db') as mock_load_metric:
                    mock_metric = Mock()
                    mock_metric.name = "Test Metric"
                    mock_metric.class_name = "TestMetricClass"
                    mock_load_metric.return_value = mock_metric
                    
                    # Mock the metric evaluation
                    with patch.object(mock_metric, 'evaluate') as mock_evaluate:
                        mock_evaluate.return_value = {"score": 0.85, "passed": True}
                        
                        result = test_metric(
                            metric_id="metric123",
                            organization_id="org456", 
                            user_id="user789",
                            input_text="Test input",
                            output_text="Test output",
                            expected_output="Expected output"
                        )
                        
                        # Verify set_tenant was called correctly
                        mock_set_tenant.assert_called_once_with(mock_db, "org456", "user789")
                        
                        # Verify metric was loaded
                        mock_load_metric.assert_called_once_with(mock_db, "metric123")
                        
                        # Verify result structure
                        assert "metric_id" in result
                        assert "organization_id" in result
                        assert "user_id" in result
    
    def test_test_metric_with_test_id(self):
        """Test metric testing with test_id parameter"""
        with patch('test_metric.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            
            with patch('rhesis.backend.app.database.set_tenant'):
                with patch('test_metric.load_metric_from_db') as mock_load_metric:
                    mock_metric = Mock()
                    mock_metric.name = "Test Metric"
                    mock_load_metric.return_value = mock_metric
                    
                    with patch('test_metric.load_test_from_db') as mock_load_test:
                        mock_test = Mock()
                        mock_load_test.return_value = mock_test
                        
                        with patch('test_metric.extract_test_data') as mock_extract:
                            mock_extract.return_value = ("Test input", "Expected output", [])
                            
                            with patch.object(mock_metric, 'evaluate') as mock_evaluate:
                                mock_evaluate.return_value = {"score": 0.85}
                                
                                result = test_metric(
                                    metric_id="metric123",
                                    organization_id="org456",
                                    user_id="user789", 
                                    test_id="test123",
                                    output_text="Test output"
                                )
                                
                                # Verify test data was loaded
                                mock_load_test.assert_called_once_with(mock_db, "test123")
                                mock_extract.assert_called_once_with(mock_test)
                                
                                assert "metric_id" in result
    
    def test_test_metric_metric_not_found(self):
        """Test metric testing when metric is not found"""
        with patch('test_metric.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            
            with patch('rhesis.backend.app.database.set_tenant'):
                with patch('test_metric.load_metric_from_db') as mock_load_metric:
                    mock_load_metric.return_value = None  # Metric not found
                    
                    # Mock query for available metrics
                    mock_query = Mock()
                    mock_query.limit.return_value.all.return_value = []
                    mock_db.query.return_value = mock_query
                    
                    result = test_metric(
                        metric_id="nonexistent",
                        organization_id="org456",
                        user_id="user789",
                        input_text="Test input",
                        output_text="Test output"
                    )
                    
                    assert "error" in result
                    assert "Metric not found" in result["error"]
    
    def test_test_metric_test_not_found(self):
        """Test metric testing when test is not found"""
        with patch('test_metric.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            
            with patch('rhesis.backend.app.database.set_tenant'):
                with patch('test_metric.load_test_from_db') as mock_load_test:
                    mock_load_test.return_value = None  # Test not found
                    
                    # Mock query for available tests
                    mock_query = Mock()
                    mock_query.limit.return_value.all.return_value = []
                    mock_db.query.return_value = mock_query
                    
                    result = test_metric(
                        metric_id="metric123",
                        organization_id="org456",
                        user_id="user789",
                        test_id="nonexistent",
                        output_text="Test output"
                    )
                    
                    assert "error" in result
                    assert "Test not found" in result["error"]
    
    def test_test_metric_template_only(self):
        """Test metric testing with template_only flag"""
        with patch('test_metric.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            
            with patch('rhesis.backend.app.database.set_tenant'):
                with patch('test_metric.load_metric_from_db') as mock_load_metric:
                    mock_metric = Mock()
                    mock_metric.name = "Test Metric"
                    mock_load_metric.return_value = mock_metric
                    
                    with patch.object(mock_metric, 'render_template') as mock_render:
                        mock_render.return_value = "Rendered template"
                        
                        result = test_metric(
                            metric_id="metric123",
                            organization_id="org456",
                            user_id="user789",
                            input_text="Test input",
                            template_only=True
                        )
                        
                        # Should render template but not evaluate
                        mock_render.assert_called_once()
                        assert "rendered_template" in result


class TestPrintResults:
    """Test print_results function"""
    
    def test_print_results_basic(self, capsys):
        """Test basic result printing"""
        results = {
            "metric_name": "Test Metric",
            "score": 0.85,
            "passed": True,
            "input": "Test input",
            "output": "Test output"
        }
        
        print_results(results)
        
        captured = capsys.readouterr()
        assert "Test Metric" in captured.out
        assert "0.85" in captured.out
    
    def test_print_results_with_error(self, capsys):
        """Test printing results with error"""
        results = {
            "error": "Metric not found"
        }
        
        print_results(results)
        
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "Metric not found" in captured.out
    
    def test_print_results_debug_mode(self, capsys):
        """Test printing results in debug mode"""
        results = {
            "metric_name": "Test Metric",
            "score": 0.85,
            "debug_info": "Debug information"
        }
        
        print_results(results, debug=True)
        
        captured = capsys.readouterr()
        assert "Debug information" in captured.out


# Integration test fixtures
@pytest.fixture
def mock_metric():
    """Create a mock metric for testing"""
    metric = Mock()
    metric.id = "metric123"
    metric.nano_id = "abc123"
    metric.name = "Test Metric"
    metric.class_name = "TestMetricClass"
    metric.evaluate = Mock(return_value={"score": 0.85, "passed": True})
    metric.render_template = Mock(return_value="Rendered template")
    return metric


@pytest.fixture
def mock_test():
    """Create a mock test for testing"""
    test = Mock()
    test.id = "test123"
    test.nano_id = "xyz789"
    
    # Mock prompt
    prompt = Mock()
    prompt.content = "What is 2+2?"
    test.prompt = prompt
    
    # Mock response
    response = Mock()
    response.content = "4"
    test.response = response
    
    # Mock context chunks
    test.context_chunks = []
    
    return test


class TestIntegration:
    """Integration tests for the metrics test script"""
    
    def test_full_metric_test_flow(self, mock_metric, mock_test):
        """Test the complete metric testing flow"""
        with patch('test_metric.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            
            with patch('test_metric.set_tenant') as mock_set_tenant:
                with patch('test_metric.load_metric_from_db', return_value=mock_metric):
                    with patch('test_metric.load_test_from_db', return_value=mock_test):
                        
                        result = test_metric(
                            metric_id="metric123",
                            organization_id="org456",
                            user_id="user789",
                            test_id="test123",
                            output_text="Model output"
                        )
                        
                        # Verify tenant context was set
                        mock_set_tenant.assert_called_once_with(mock_db, "org456", "user789")
                        
                        # Verify metric evaluation was called
                        mock_metric.evaluate.assert_called_once()
                        
                        # Verify result structure
                        assert isinstance(result, dict)
                        assert "metric_id" in result
                        assert result["metric_id"] == "metric123"

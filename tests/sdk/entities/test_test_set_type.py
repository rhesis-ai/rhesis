"""Tests for test set type functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from rhesis.sdk.entities.test_set import TestSet


class TestTestSetType:
    """Tests for test set type functionality."""

    def test_test_set_init_with_test_set_type(self):
        """Test TestSet initialization with test_set_type."""
        test_set = TestSet(
            name="Test Set",
            description="Test description",
            test_set_type="Multi-Turn"
        )
        
        assert test_set.test_set_type == "Multi-Turn"

    def test_test_set_init_without_test_set_type_defaults_to_single_turn(self):
        """Test TestSet initialization without test_set_type defaults to Single-Turn."""
        test_set = TestSet(
            name="Test Set",
            description="Test description"
        )
        
        assert test_set.test_set_type == "Single-Turn"

    def test_test_set_init_with_explicit_single_turn(self):
        """Test TestSet initialization with explicit Single-Turn type."""
        test_set = TestSet(
            name="Test Set",
            description="Test description",
            test_set_type="Single-Turn"
        )
        
        assert test_set.test_set_type == "Single-Turn"

    def test_prepare_test_set_data_includes_test_set_type(self):
        """Test that _prepare_test_set_data includes test_set_type."""
        test_set = TestSet(
            name="Test Set",
            description="Test description",
            short_description="Short desc",
            test_set_type="Multi-Turn",
            tests=[{"content": "test content"}]
        )
        
        data = test_set._prepare_test_set_data()
        
        assert data["test_set_type"] == "Multi-Turn"
        assert data["name"] == "Test Set"
        assert data["description"] == "Test description"
        assert data["short_description"] == "Short desc"
        assert len(data["tests"]) == 1

    def test_prepare_test_set_data_with_default_type(self):
        """Test that _prepare_test_set_data includes default test_set_type."""
        test_set = TestSet(
            name="Test Set",
            description="Test description",
            tests=[{"content": "test content"}]
        )
        
        data = test_set._prepare_test_set_data()
        
        assert data["test_set_type"] == "Single-Turn"

    def test_update_from_response_updates_test_set_type(self):
        """Test that _update_from_response updates test_set_type."""
        test_set = TestSet(
            name="Test Set",
            test_set_type="Single-Turn"
        )
        
        response_data = {
            "id": "123",
            "name": "Updated Test Set",
            "test_set_type": "Multi-Turn"
        }
        
        test_set._update_from_response(response_data)
        
        assert test_set.test_set_type == "Multi-Turn"
        assert test_set.name == "Updated Test Set"
        assert test_set.fields["id"] == "123"

    def test_update_from_response_without_test_set_type(self):
        """Test that _update_from_response works without test_set_type in response."""
        test_set = TestSet(
            name="Test Set",
            test_set_type="Single-Turn"
        )
        
        response_data = {
            "id": "123",
            "name": "Updated Test Set"
        }
        
        test_set._update_from_response(response_data)
        
        # Should keep original test_set_type
        assert test_set.test_set_type == "Single-Turn"
        assert test_set.name == "Updated Test Set"


class TestTestSetUploadWithType:
    """Tests for test set upload with type functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        client = Mock()
        client.get_url.return_value = "http://test.com/test_sets/bulk"
        return client

    @pytest.fixture
    def test_set_with_type(self):
        """Create a test set with type for testing."""
        test_set = TestSet(
            name="Multi-Turn Test Set",
            description="A test set for multi-turn conversations",
            short_description="Multi-turn tests",
            test_set_type="Multi-Turn",
            tests=[
                {"content": "First turn"},
                {"content": "Second turn"}
            ]
        )
        test_set.client = Mock()
        test_set.client.get_url.return_value = "http://test.com/test_sets/bulk"
        test_set.headers = {"Authorization": "Bearer test_token"}
        return test_set

    @patch('requests.post')
    @patch('tqdm.tqdm')
    def test_upload_includes_test_set_type(self, mock_tqdm, mock_post, test_set_with_type):
        """Test that upload includes test_set_type in the request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "id": "test_id_123",
            "name": "Multi-Turn Test Set",
            "test_set_type": "Multi-Turn"
        }
        mock_post.return_value = mock_response
        
        # Mock progress bar
        mock_pbar = Mock()
        mock_tqdm.return_value.__enter__.return_value = mock_pbar
        
        # Perform upload
        test_set_with_type.upload()
        
        # Verify the request was made with correct data
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL
        assert call_args[0][0] == "http://test.com/test_sets/bulk"
        
        # Check JSON payload
        json_data = call_args[1]["json"]
        assert json_data["name"] == "Multi-Turn Test Set"
        assert json_data["description"] == "A test set for multi-turn conversations"
        assert json_data["test_set_type"] == "Multi-Turn"
        assert len(json_data["tests"]) == 2

    @patch('requests.post')
    @patch('tqdm.tqdm')
    def test_upload_with_default_type(self, mock_tqdm, mock_post, mock_client):
        """Test that upload works with default test_set_type."""
        test_set = TestSet(
            name="Default Test Set",
            description="A test set with default type",
            tests=[{"content": "test content"}]
        )
        test_set.client = mock_client
        test_set.headers = {"Authorization": "Bearer test_token"}
        
        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "id": "test_id_456",
            "name": "Default Test Set",
            "test_set_type": "Single-Turn"
        }
        mock_post.return_value = mock_response
        
        # Mock progress bar
        mock_pbar = Mock()
        mock_tqdm.return_value.__enter__.return_value = mock_pbar
        
        # Perform upload
        test_set.upload()
        
        # Verify the request was made with correct data
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check JSON payload
        json_data = call_args[1]["json"]
        assert json_data["name"] == "Default Test Set"
        assert json_data["test_set_type"] == "Single-Turn"

    def test_upload_fails_without_tests(self):
        """Test that upload fails when no tests are provided."""
        test_set = TestSet(
            name="Empty Test Set",
            description="A test set without tests",
            test_set_type="Single-Turn"
        )
        
        with pytest.raises(ValueError, match="No tests to upload"):
            test_set.upload()

    def test_upload_fails_with_empty_tests(self):
        """Test that upload fails when tests list is empty."""
        test_set = TestSet(
            name="Empty Test Set",
            description="A test set with empty tests",
            test_set_type="Single-Turn",
            tests=[]
        )
        
        with pytest.raises(ValueError, match="No tests to upload"):
            test_set.upload()


class TestTestSetTypeIntegration:
    """Integration tests for test set type functionality."""

    def test_full_workflow_with_multi_turn_type(self):
        """Test full workflow with Multi-Turn test set type."""
        # Create test set
        test_set = TestSet(
            name="Integration Test Set",
            description="Full workflow test",
            short_description="Integration test",
            test_set_type="Multi-Turn",
            tests=[
                {"content": "Turn 1: Hello"},
                {"content": "Turn 2: How are you?"},
                {"content": "Turn 3: Goodbye"}
            ]
        )
        
        # Verify initial state
        assert test_set.test_set_type == "Multi-Turn"
        assert len(test_set.tests) == 3
        
        # Test data preparation
        data = test_set._prepare_test_set_data()
        assert data["test_set_type"] == "Multi-Turn"
        assert len(data["tests"]) == 3
        
        # Test response update
        response_data = {
            "id": "integration_test_123",
            "name": "Integration Test Set",
            "test_set_type": "Multi-Turn",
            "metadata": {"created_by": "test"}
        }
        
        test_set._update_from_response(response_data)
        
        assert test_set.fields["id"] == "integration_test_123"
        assert test_set.test_set_type == "Multi-Turn"
        assert test_set.metadata == {"created_by": "test"}

    def test_type_consistency_across_operations(self):
        """Test that test_set_type remains consistent across operations."""
        # Start with Single-Turn
        test_set = TestSet(
            name="Consistency Test",
            test_set_type="Single-Turn",
            tests=[{"content": "single turn test"}]
        )
        
        assert test_set.test_set_type == "Single-Turn"
        
        # Prepare data
        data = test_set._prepare_test_set_data()
        assert data["test_set_type"] == "Single-Turn"
        
        # Simulate backend response changing type
        response_data = {
            "id": "consistency_test_456",
            "test_set_type": "Multi-Turn"
        }
        
        test_set._update_from_response(response_data)
        
        # Type should be updated
        assert test_set.test_set_type == "Multi-Turn"
        
        # Prepare data again
        data = test_set._prepare_test_set_data()
        assert data["test_set_type"] == "Multi-Turn"

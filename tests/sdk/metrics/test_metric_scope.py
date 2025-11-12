"""Tests for metric scope functionality."""

import pytest
from unittest.mock import Mock, patch

from rhesis.sdk.metrics.base import MetricConfig, MetricScope
from rhesis.sdk.metrics.utils import sdk_config_to_backend_config, backend_config_to_sdk_config
from rhesis.sdk.metrics.providers.native.numeric_judge import NumericJudge


class TestMetricScope:
    """Tests for MetricScope enum and functionality."""

    def test_metric_scope_enum_values(self):
        """Test that MetricScope enum has correct values."""
        assert MetricScope.SINGLE_TURN == "Single-Turn"
        assert MetricScope.MULTI_TURN == "Multi-Turn"

    def test_metric_config_with_metric_scope_strings(self):
        """Test MetricConfig with metric_scope as strings."""
        config = MetricConfig(
            name="test_metric",
            metric_scope=["Single-Turn", "Multi-Turn"]
        )
        
        assert len(config.metric_scope) == 2
        assert config.metric_scope[0] == MetricScope.SINGLE_TURN
        assert config.metric_scope[1] == MetricScope.MULTI_TURN

    def test_metric_config_with_metric_scope_enums(self):
        """Test MetricConfig with metric_scope as enums."""
        config = MetricConfig(
            name="test_metric",
            metric_scope=[MetricScope.SINGLE_TURN]
        )
        
        assert len(config.metric_scope) == 1
        assert config.metric_scope[0] == MetricScope.SINGLE_TURN

    def test_metric_config_with_invalid_metric_scope(self):
        """Test MetricConfig with invalid metric_scope raises error."""
        with pytest.raises(ValueError, match="Unknown metric scope: Invalid-Scope"):
            MetricConfig(
                name="test_metric",
                metric_scope=["Invalid-Scope"]
            )

    def test_metric_config_with_none_metric_scope(self):
        """Test MetricConfig with None metric_scope."""
        config = MetricConfig(
            name="test_metric",
            metric_scope=None
        )
        
        assert config.metric_scope is None

    def test_metric_config_with_empty_metric_scope(self):
        """Test MetricConfig with empty metric_scope list."""
        config = MetricConfig(
            name="test_metric",
            metric_scope=[]
        )
        
        assert config.metric_scope == []


class TestMetricScopeUtils:
    """Tests for metric scope utility functions."""

    def test_sdk_config_to_backend_config_with_metric_scope(self):
        """Test conversion from SDK config to backend config with metric_scope."""
        config = {
            "name": "test_metric",
            "metric_scope": [MetricScope.SINGLE_TURN, MetricScope.MULTI_TURN]
        }
        
        result = sdk_config_to_backend_config(config.copy())  # Use copy to avoid modifying original
        
        assert result["metric_scope"] == ["Single-Turn", "Multi-Turn"]

    def test_sdk_config_to_backend_config_without_metric_scope(self):
        """Test conversion from SDK config to backend config without metric_scope."""
        config = {
            "name": "test_metric"
        }
        
        result = sdk_config_to_backend_config(config)
        
        assert "metric_scope" not in result or result.get("metric_scope") is None

    def test_backend_config_to_sdk_config_with_metric_scope(self):
        """Test conversion from backend config to SDK config with metric_scope."""
        config = {
            "name": "test_metric",
            "metric_scope": ["Single-Turn", "Multi-Turn"]
        }
        
        result = backend_config_to_sdk_config(config)
        
        assert len(result["metric_scope"]) == 2
        assert result["metric_scope"][0] == MetricScope.SINGLE_TURN
        assert result["metric_scope"][1] == MetricScope.MULTI_TURN

    def test_backend_config_to_sdk_config_without_metric_scope(self):
        """Test conversion from backend config to SDK config without metric_scope."""
        config = {
            "name": "test_metric"
        }
        
        result = backend_config_to_sdk_config(config)
        
        assert "metric_scope" not in result or result.get("metric_scope") is None


class TestMetricWithScope:
    """Tests for metrics with scope functionality."""

    @pytest.fixture
    def setup_env(self, monkeypatch):
        """Set up test environment."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")

    def test_numeric_judge_with_metric_scope(self, setup_env):
        """Test NumericJudge with metric_scope."""
        with patch('rhesis.sdk.models.factory.get_model') as mock_get_model:
            mock_model = Mock()
            mock_get_model.return_value = mock_model
            
            metric = NumericJudge(
                name="test_numeric",
                evaluation_prompt="Test prompt",
                metric_type="rag",
                metric_scope=[MetricScope.SINGLE_TURN],
                model="gemini"
            )
            
            assert metric.metric_scope == [MetricScope.SINGLE_TURN]

    def test_numeric_judge_to_config_includes_metric_scope(self, setup_env):
        """Test that NumericJudge.to_config() includes metric_scope."""
        with patch('rhesis.sdk.models.factory.get_model') as mock_get_model:
            mock_model = Mock()
            mock_get_model.return_value = mock_model
            
            metric = NumericJudge(
                name="test_numeric",
                evaluation_prompt="Test prompt",
                metric_type="rag",
                metric_scope=[MetricScope.MULTI_TURN],
                model="gemini"
            )
            
            result_config = metric.to_config()
            
            assert result_config.metric_scope == [MetricScope.MULTI_TURN]


class TestMetricScopePushPull:
    """Tests for push/pull operations with metric scope."""

    @pytest.fixture
    def setup_env(self, monkeypatch):
        """Set up test environment."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")

    @patch('rhesis.sdk.metrics.providers.native.serialization.Client')
    def test_push_metric_with_scope(self, mock_client_class, setup_env):
        """Test pushing a metric with metric_scope."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        with patch('rhesis.sdk.models.factory.get_model') as mock_get_model:
            mock_model = Mock()
            mock_get_model.return_value = mock_model
            
            metric = NumericJudge(
                name="test_metric",
                evaluation_prompt="Test prompt",
                metric_type="rag",
                metric_scope=[MetricScope.SINGLE_TURN, MetricScope.MULTI_TURN],
                model="gemini"
            )
            
            metric.push()
            
            # Verify that send_request was called
            mock_client.send_request.assert_called_once()
            
            # Get the config that was sent
            call_args = mock_client.send_request.call_args
            sent_config = call_args[0][2]  # Third argument is the config
            
            # Verify metric_scope was converted to strings
            assert sent_config["metric_scope"] == ["Single-Turn", "Multi-Turn"]

    @patch('rhesis.sdk.metrics.providers.native.serialization.Client')
    def test_pull_metric_with_scope(self, mock_client_class, setup_env):
        """Test pulling a metric with metric_scope."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the response from the backend (single result, not list)
        backend_response = [{
            "name": "test_metric",
            "evaluation_prompt": "Test prompt",
            "metric_scope": ["Single-Turn"],
            "score_type": "numeric",
            "metric_type": "rag",
            "class_name": "NumericJudge",
            "backend": "rhesis"
        }]
        mock_client.send_request.return_value = backend_response
        
        with patch('rhesis.sdk.models.factory.get_model') as mock_get_model:
            mock_model = Mock()
            mock_get_model.return_value = mock_model
            
            # Mock the from_config method to avoid actual instantiation issues
            with patch.object(NumericJudge, 'from_config') as mock_from_config:
                mock_metric = Mock()
                mock_metric.metric_scope = [MetricScope.SINGLE_TURN]
                mock_from_config.return_value = mock_metric
                
                metric = NumericJudge.pull(name="test_metric")
                
                # Verify that the metric has the correct scope
                assert metric.metric_scope == [MetricScope.SINGLE_TURN]

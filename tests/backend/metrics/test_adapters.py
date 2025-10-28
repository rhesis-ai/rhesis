"""
Tests for the metrics adapter layer (backend → SDK).

These tests validate that the adapter correctly:
- Maps RhesisPromptMetric to SDK classes based on score_type
- Converts backend types to SDK frameworks
- Extracts and transforms parameters correctly
- Handles edge cases and errors gracefully
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.metrics.adapters import (
    BACKEND_TO_FRAMEWORK_MAP,
    build_metric_params_from_config,
    build_metric_params_from_model,
    create_metric,
    create_metric_from_config,
    create_metric_from_db_model,
    map_backend_type_to_framework,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_metric_model_numeric():
    """Create a mock numeric NumericJudge model."""
    model = Mock(spec=MetricModel)
    model.id = uuid4()
    model.name = "Test Numeric Metric"
    model.description = "Test numeric metric"
    model.class_name = "NumericJudge"
    model.score_type = "numeric"
    model.evaluation_prompt = "Rate the accuracy from 1 to 5"
    model.evaluation_steps = "Step 1, Step 2"
    model.reasoning = "Because..."
    model.min_score = 1.0
    model.max_score = 5.0
    model.threshold = 3.0
    model.threshold_operator = ">="
    model.ground_truth_required = False
    model.context_required = False
    model.model_id = None
    model.evaluation_examples = None
    model.backend_type = Mock(type_value="rhesis")
    return model


@pytest.fixture
def mock_metric_model_categorical():
    """Create a mock categorical CategoricalJudge model."""
    model = Mock(spec=MetricModel)
    model.id = uuid4()
    model.name = "Test Categorical Metric"
    model.description = "Test categorical metric"
    model.class_name = "CategoricalJudge"
    model.score_type = "categorical"
    model.evaluation_prompt = "Rate as poor/good/excellent"
    model.evaluation_steps = None
    model.reasoning = None
    model.reference_score = "excellent"  # Deprecated but kept for transition
    model.categories = ["excellent", "good", "poor"]
    model.passing_categories = ["excellent"]
    model.min_score = None
    model.max_score = None
    model.threshold = None
    model.threshold_operator = "="
    model.ground_truth_required = True
    model.context_required = False
    model.model_id = None
    model.evaluation_examples = None
    model.backend_type = Mock(type_value="rhesis")
    return model


@pytest.fixture
def mock_metric_model_ragas():
    """Create a mock Ragas metric model."""
    model = Mock(spec=MetricModel)
    model.id = uuid4()
    model.name = "Answer Relevancy"
    model.description = "Ragas answer relevancy"
    model.class_name = "RagasAnswerRelevancy"
    model.score_type = "numeric"
    model.evaluation_prompt = None
    model.evaluation_steps = None
    model.reasoning = None
    model.min_score = 0.0
    model.max_score = 1.0
    model.threshold = 0.7
    model.threshold_operator = ">="
    model.ground_truth_required = False
    model.context_required = True
    model.model_id = None
    model.backend_type = Mock(type_value="ragas")
    return model


@pytest.fixture
def metric_config_numeric():
    """Create a numeric metric config dict."""
    return {
        "name": "Test Numeric Config",
        "class_name": "NumericJudge",
        "backend": "rhesis",
        "description": "Test numeric from config",
        "threshold": 3.0,
        "threshold_operator": ">=",
        "parameters": {
            "score_type": "numeric",
            "evaluation_prompt": "Rate accuracy 1-5",
            "min_score": 1.0,
            "max_score": 5.0,
        },
    }


@pytest.fixture
def metric_config_categorical():
    """Create a categorical metric config dict."""
    return {
        "name": "Test Categorical Config",
        "class_name": "CategoricalJudge",
        "backend": "rhesis",
        "description": "Test categorical from config",
        "categories": ["good", "poor", "excellent"],
        "passing_categories": ["good", "excellent"],
        "parameters": {
            "score_type": "categorical",
            "evaluation_prompt": "Rate as poor/good/excellent",
        },
    }


# ============================================================================
# TEST CLASS NAME MAPPING
# ============================================================================


# NOTE: TestGetSdkClassName removed after adapter simplification
# The database now stores SDK-compatible class names directly (NumericJudge, CategoricalJudge)
# No mapping function needed anymore - see migration phases 1-7


class TestMapBackendTypeToFramework:
    """Test backend type to framework mapping."""

    def test_rhesis_mapping(self):
        """Test rhesis → rhesis."""
        assert map_backend_type_to_framework("rhesis") == "rhesis"

    def test_deepeval_mapping(self):
        """Test deepeval → deepeval."""
        assert map_backend_type_to_framework("deepeval") == "deepeval"

    def test_ragas_mapping(self):
        """Test ragas → ragas."""
        assert map_backend_type_to_framework("ragas") == "ragas"

    def test_custom_mappings(self):
        """Test custom types → rhesis."""
        assert map_backend_type_to_framework("custom") == "rhesis"
        assert map_backend_type_to_framework("custom-code") == "rhesis"
        assert map_backend_type_to_framework("custom-prompt") == "rhesis"

    def test_none_defaults_rhesis(self):
        """Test None backend type defaults to rhesis."""
        assert map_backend_type_to_framework(None) == "rhesis"

    def test_unknown_passes_through(self):
        """Test unknown backend types pass through."""
        assert map_backend_type_to_framework("unknown") == "unknown"


# ============================================================================
# TEST PARAMETER BUILDING
# ============================================================================


class TestBuildMetricParamsFromModel:
    """Test parameter extraction from DB models."""

    def test_numeric_params(self, mock_metric_model_numeric):
        """Test numeric metric parameter extraction."""
        params = build_metric_params_from_model(mock_metric_model_numeric)

        assert params["name"] == "Test Numeric Metric"
        assert params["description"] == "Test numeric metric"
        assert params["evaluation_prompt"] == "Rate the accuracy from 1 to 5"
        assert params["evaluation_steps"] == "Step 1, Step 2"
        assert params["reasoning"] == "Because..."
        assert params["min_score"] == 1.0
        assert params["max_score"] == 5.0
        assert params["threshold"] == 3.0
        assert params["threshold_operator"] == ">="
        assert params["requires_ground_truth"] is False
        assert params["requires_context"] is False

    def test_categorical_params(self, mock_metric_model_categorical):
        """Test categorical metric parameter extraction."""
        params = build_metric_params_from_model(mock_metric_model_categorical)

        assert params["name"] == "Test Categorical Metric"
        # Categories are now stored directly in database
        assert params["categories"] == ["excellent", "good", "poor"]
        assert params["passing_categories"] == ["excellent"]
        assert params["requires_ground_truth"] is True
        assert "min_score" not in params  # Categorical doesn't have numeric scores
        assert "max_score" not in params

    def test_missing_optional_fields(self):
        """Test handling of missing optional fields."""
        model = Mock(spec=MetricModel)
        model.id = uuid4()
        model.name = "Minimal Metric"
        model.description = None
        model.evaluation_prompt = None
        model.evaluation_steps = None
        model.reasoning = None
        model.score_type = "numeric"
        model.min_score = None
        model.max_score = None
        model.threshold = None
        model.threshold_operator = None
        model.ground_truth_required = None
        model.context_required = None
        model.model_id = None

        params = build_metric_params_from_model(model)

        assert params["name"] == "Minimal Metric"
        assert params["description"] is None
        # SDK factory requires these fields, so they get defaults
        assert "evaluation_prompt" in params
        assert "evaluation_steps" in params
        assert "reasoning" in params
        # Other optional fields should not be in params if None
        assert "min_score" not in params


class TestBuildMetricParamsFromConfig:
    """Test parameter extraction from config dicts."""

    def test_numeric_config_params(self, metric_config_numeric):
        """Test numeric metric config parameter extraction."""
        params = build_metric_params_from_config(metric_config_numeric)

        assert params["name"] == "Test Numeric Config"
        assert params["description"] == "Test numeric from config"
        assert params["evaluation_prompt"] == "Rate accuracy 1-5"
        assert params["min_score"] == 1.0
        assert params["max_score"] == 5.0
        assert params["threshold"] == 3.0
        assert params["threshold_operator"] == ">="

    def test_categorical_config_params(self, metric_config_categorical):
        """Test categorical metric config parameter extraction."""
        params = build_metric_params_from_config(metric_config_categorical)

        assert params["name"] == "Test Categorical Config"
        # Categories are now provided directly in config (no conversion needed)
        assert params["categories"] == ["good", "poor", "excellent"]
        assert params["passing_categories"] == ["good", "excellent"]
        assert params["evaluation_prompt"] == "Rate as poor/good/excellent"


# ============================================================================
# TEST METRIC CREATION FROM DB MODELS
# ============================================================================


class TestCreateMetricFromDbModel:
    """Test creating SDK metrics from database models."""

    @patch("rhesis.backend.metrics.adapters.MetricFactory.create")
    def test_create_numeric_metric(self, mock_factory_create, mock_metric_model_numeric):
        """Test creating SDK metric from numeric DB model."""
        mock_factory_create.return_value = Mock()

        result = create_metric_from_db_model(mock_metric_model_numeric)

        assert result is not None
        mock_factory_create.assert_called_once()

        # Verify correct arguments
        call_args = mock_factory_create.call_args
        assert call_args[0][0] == "rhesis"  # framework
        assert call_args[0][1] == "NumericJudge"  # SDK class name

    @patch("rhesis.backend.metrics.adapters.MetricFactory.create")
    def test_create_categorical_metric(
        self, mock_factory_create, mock_metric_model_categorical
    ):
        """Test creating SDK metric from categorical DB model."""
        mock_factory_create.return_value = Mock()

        result = create_metric_from_db_model(mock_metric_model_categorical)

        assert result is not None
        mock_factory_create.assert_called_once()

        # Verify correct arguments
        call_args = mock_factory_create.call_args
        assert call_args[0][0] == "rhesis"  # framework
        assert call_args[0][1] == "CategoricalJudge"  # SDK class name

    @patch("rhesis.backend.metrics.adapters.MetricFactory.create")
    def test_create_ragas_metric(self, mock_factory_create, mock_metric_model_ragas):
        """Test creating SDK metric from Ragas DB model."""
        mock_factory_create.return_value = Mock()

        result = create_metric_from_db_model(mock_metric_model_ragas)

        assert result is not None
        mock_factory_create.assert_called_once()

        # Verify correct arguments
        call_args = mock_factory_create.call_args
        assert call_args[0][0] == "ragas"  # framework
        assert call_args[0][1] == "RagasAnswerRelevancy"  # class name unchanged

    def test_missing_class_name(self):
        """Test handling of missing class_name."""
        model = Mock(spec=MetricModel)
        model.id = uuid4()
        model.class_name = None

        result = create_metric_from_db_model(model)

        assert result is None

    @patch("rhesis.backend.metrics.adapters.MetricFactory.create")
    def test_factory_exception_handled(self, mock_factory_create, mock_metric_model_numeric):
        """Test that factory exceptions are caught and logged."""
        mock_factory_create.side_effect = Exception("Factory error")

        result = create_metric_from_db_model(mock_metric_model_numeric)

        assert result is None  # Should return None on error


# ============================================================================
# TEST METRIC CREATION FROM CONFIG DICTS
# ============================================================================


class TestCreateMetricFromConfig:
    """Test creating SDK metrics from config dicts."""

    @patch("rhesis.backend.metrics.adapters.MetricFactory.create")
    def test_create_from_numeric_config(self, mock_factory_create, metric_config_numeric):
        """Test creating SDK metric from numeric config dict."""
        mock_factory_create.return_value = Mock()

        result = create_metric_from_config(metric_config_numeric)

        assert result is not None
        mock_factory_create.assert_called_once()

        call_args = mock_factory_create.call_args
        assert call_args[0][0] == "rhesis"
        assert call_args[0][1] == "NumericJudge"

    @patch("rhesis.backend.metrics.adapters.MetricFactory.create")
    def test_create_from_categorical_config(
        self, mock_factory_create, metric_config_categorical
    ):
        """Test creating SDK metric from categorical config dict."""
        mock_factory_create.return_value = Mock()

        result = create_metric_from_config(metric_config_categorical)

        assert result is not None
        mock_factory_create.assert_called_once()

        call_args = mock_factory_create.call_args
        assert call_args[0][0] == "rhesis"
        assert call_args[0][1] == "CategoricalJudge"

    def test_missing_class_name_in_config(self):
        """Test handling of missing class_name in config."""
        config = {"backend": "rhesis"}  # Missing class_name

        result = create_metric_from_config(config)

        assert result is None


# ============================================================================
# TEST UNIVERSAL CREATE METRIC FUNCTION
# ============================================================================


class TestCreateMetric:
    """Test universal create_metric function."""

    @patch("rhesis.backend.metrics.adapters.create_metric_from_db_model")
    def test_routes_to_db_model(self, mock_create_db, mock_metric_model_numeric):
        """Test that MetricModel instances route to create_metric_from_db_model."""
        mock_create_db.return_value = Mock()

        create_metric(mock_metric_model_numeric)

        mock_create_db.assert_called_once_with(mock_metric_model_numeric, None)

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_routes_to_config(self, mock_create_config, metric_config_numeric):
        """Test that dict instances route to create_metric_from_config."""
        mock_create_config.return_value = Mock()

        create_metric(metric_config_numeric)

        mock_create_config.assert_called_once_with(metric_config_numeric, None)

    def test_invalid_type(self):
        """Test handling of invalid input type."""
        result = create_metric("invalid")  # String is not valid

        assert result is None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestAdapterIntegration:
    """Integration tests with real SDK (if available)."""

    @pytest.mark.skipif(
        not hasattr(__import__("rhesis.sdk.metrics", fromlist=["NumericJudge"]), "NumericJudge"),
        reason="SDK metrics not available"
    )
    @patch("rhesis.backend.metrics.adapters.MetricFactory.create")
    def test_end_to_end_numeric(self, mock_factory_create, mock_metric_model_numeric):
        """Test complete flow from DB model to SDK metric instance."""
        # This would create a real SDK metric if SDK is available
        mock_factory_create.return_value = Mock()
        
        metric = create_metric_from_db_model(mock_metric_model_numeric)
        
        assert metric is not None


# ============================================================================
# TEST FUTURE NAMING COMPATIBILITY
# ============================================================================


class TestFutureNamingMigration:
    """Test that adapter configuration is complete."""

    # NOTE: CLASS_NAME_MAP tests removed after adapter simplification
    # Database now stores SDK class names directly, no mapping needed

    def test_backend_framework_map_complete(self):
        """Verify all expected backend types have framework mappings."""
        expected_backends = [
            "rhesis",
            "deepeval",
            "ragas",
            "custom",
            "custom-code",
            "custom-prompt",
        ]
        for backend in expected_backends:
            assert backend in BACKEND_TO_FRAMEWORK_MAP


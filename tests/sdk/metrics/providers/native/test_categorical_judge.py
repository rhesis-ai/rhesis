from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.metrics.base import MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.categorical_judge import (
    CategoricalJudge,
    PromptMetricCategoricalConfig,
)


@pytest.fixture
def metric(monkeypatch):
    monkeypatch.setenv("RHESIS_API_KEY", "test_api_key")
    return CategoricalJudge(
        evaluation_prompt="test_prompt",
        name="test_metric",
        description="test_description",
        evaluation_steps="test_steps",
        reasoning="test_reasoning",
        evaluation_examples="test_examples",
        categories=["test_category1", "test_category2"],
        passing_categories="test_category1",
    )


def test_categorical_judge__init__(metric):
    assert metric.evaluation_prompt == "test_prompt"
    assert metric.evaluation_steps == "test_steps"
    assert metric.reasoning == "test_reasoning"
    assert metric.evaluation_examples == "test_examples"
    assert metric.name == "test_metric"
    assert metric.description == "test_description"
    assert metric.metric_type == MetricType.RAG
    assert metric.score_type == ScoreType.CATEGORICAL


def test_validate_categories():
    config = PromptMetricCategoricalConfig(
        categories=["test_category1", "test_category2"],
        passing_categories="test_category1",
    )
    config._validate_categories()

    with pytest.raises(ValueError):
        config.categories = ["test_category1"]
        config._validate_categories()


def test_validate_passing_categories(metric):
    config = PromptMetricCategoricalConfig(
        categories=["test_category1", "test_category2"],
        passing_categories="test_category1",
    )
    config._validate_passing_categories()

    with pytest.raises(ValueError):
        config.passing_categories = 1
        config._validate_passing_categories()


def test_normalize_passing_categories(metric):
    config = PromptMetricCategoricalConfig(
        categories=["test_category1", "test_category2"],
        passing_categories="test_category1",
    )
    assert config.passing_categories == ["test_category1"]


def test_validate_passing_categories_subset(metric):
    config = PromptMetricCategoricalConfig(
        categories=["test_category1", "test_category2"],
        passing_categories="test_category1",
    )
    config._validate_passing_categories_subset()

    with pytest.raises(ValueError):
        config.categories = ["test_category1", "test_category2"]
        config.passing_categories = [
            "test_category1",
            "test_category2",
            "test_category3",
        ]
        config._validate_passing_categories_subset()

    with pytest.raises(ValueError):
        config.categories = ["test_category1", "test_category2"]
        config.passing_categories = ["test_category3"]
        config._validate_passing_categories_subset()


def test_evaluate_score(metric):
    assert metric._evaluate_score("test_category1", ["test_category1"]) is True
    assert metric._evaluate_score("test_category1", ["test_category2"]) is not True


def test_to_config(metric):
    assert metric.to_config().categories == ["test_category1", "test_category2"]
    assert metric.to_config().passing_categories == ["test_category1"]


def test_evaluate_successful_evaluation(metric):
    """Test successful evaluation with valid LLM response and passing score."""
    # Mock the model to return a valid response
    mock_response = Mock()
    mock_response.score = "test_category1"
    mock_response.reason = "The output correctly matches the expected category"

    with patch.object(metric.model, "generate") as mock_generate:
        mock_generate.return_value = {
            "score": "test_category1",
            "reason": "The output correctly matches the expected category",
        }

        # Call evaluate method
        result = metric.evaluate(
            input="What is the capital of France?",
            output="Paris",
            expected_output="Paris",
            context=["France is a country in Europe"],
        )

        # Verify the result
        assert isinstance(result, MetricResult)
        assert result.score == "test_category1"
        assert result.details["score"] == "test_category1"
        assert result.details["reason"] == "The output correctly matches the expected category"
        assert result.details["is_successful"] is True
        assert result.details["score_type"] == "categorical"
        assert result.details["categories"] == ["test_category1", "test_category2"]
        assert result.details["passing_categories"] == ["test_category1"]
        assert "prompt" in result.details

        # Verify model was called with correct parameters
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert "schema" in call_args.kwargs


def test_evaluate_error_handling(metric):
    """Test error handling when LLM evaluation fails."""
    # Mock the model to raise an exception
    with patch.object(metric.model, "generate") as mock_generate:
        mock_generate.side_effect = Exception("LLM service unavailable")

        # Call evaluate method
        result = metric.evaluate(
            input="What is the capital of France?",
            output="Paris",
            expected_output="Paris",
            context=["France is a country in Europe"],
        )

        # Verify error handling
        assert isinstance(result, MetricResult)
        assert result.score == "error"
        assert result.details["is_successful"] is False
        assert result.details["score_type"] == "categorical"
        assert result.details["categories"] == ["test_category1", "test_category2"]
        assert result.details["passing_categories"] == ["test_category1"]
        assert "error" in result.details
        assert "exception_type" in result.details
        assert "exception_details" in result.details
        assert "prompt" in result.details


def test_from_config_to_config(metric):
    config1 = metric.to_config()
    metric2 = CategoricalJudge.from_config(config1)
    config2 = metric2.to_config()
    assert config1 == config2

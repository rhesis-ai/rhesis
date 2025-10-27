from unittest.mock import patch

import pytest
from rhesis.sdk.metrics.base import (
    MetricResult,
    MetricType,
    ScoreType,
    ThresholdOperator,
)
from rhesis.sdk.metrics.providers.native.prompt_metric_numeric import (
    PromptMetricNumericConfig,
    RhesisPromptMetricNumeric,
)


@pytest.fixture
def metric(monkeypatch):
    monkeypatch.setenv("RHESIS_API_KEY", "test_api_key")
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    return RhesisPromptMetricNumeric(
        name="test_metric",
        description="test_description",
        evaluation_prompt="test_prompt",
        evaluation_steps="test_steps",
        reasoning="test_reasoning",
        evaluation_examples="test_examples",
        metric_type="rag",
        min_score=1,
        max_score=10,
        threshold=5,
    )


def test_prompt_metric_numeric_base__init__(metric):
    assert metric.evaluation_prompt == "test_prompt"
    assert metric.evaluation_steps == "test_steps"
    assert metric.reasoning == "test_reasoning"
    assert metric.evaluation_examples == "test_examples"
    assert metric.name == "test_metric"
    assert metric.description == "test_description"
    assert metric.metric_type == MetricType.RAG
    assert metric.score_type == ScoreType.NUMERIC


def test_validate_score_range():
    PromptMetricNumericConfig(min_score=1, max_score=10)

    with pytest.raises(ValueError):
        PromptMetricNumericConfig(min_score=1, max_score=None)
    with pytest.raises(ValueError):
        PromptMetricNumericConfig(min_score=None, max_score=1)
    with pytest.raises(ValueError):
        PromptMetricNumericConfig(min_score=1, max_score=1)

    with pytest.raises(ValueError):
        PromptMetricNumericConfig(min_score=10, max_score=1)


def test_set_score_parameters():
    config = PromptMetricNumericConfig(min_score=1, max_score=10, threshold=5)
    assert config.min_score == 1
    assert config.max_score == 10
    assert config.threshold == 5

    config = PromptMetricNumericConfig(min_score=1, max_score=10, threshold=None)
    assert config.min_score == 1
    assert config.max_score == 10
    assert config.threshold == 5.5

    with pytest.raises(ValueError):
        PromptMetricNumericConfig(min_score=1, max_score=10, threshold=11)


def test_evaluate_score(metric):
    metric.threshold_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL
    metric.threshold = 5
    assert metric._evaluate_score(5) is True
    assert metric._evaluate_score(4) is False
    assert metric._evaluate_score(6) is True

    metric.threshold_operator = ThresholdOperator.LESS_THAN_OR_EQUAL
    metric.threshold = 5
    assert metric._evaluate_score(5) is True
    assert metric._evaluate_score(4) is True
    assert metric._evaluate_score(6) is False


def test_to_config(metric):
    metric.threshold_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL
    config = metric.to_config()
    assert config.min_score == 1
    assert config.max_score == 10
    assert config.threshold == 5
    assert config.threshold_operator == ThresholdOperator.GREATER_THAN_OR_EQUAL


def test_evaluate_successful_evaluation(metric):
    """Test successful evaluation with valid LLM response and passing score."""
    # Set up metric parameters
    metric.min_score = 0.0
    metric.max_score = 10.0
    metric.threshold = 5.0
    metric.threshold_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL

    with patch.object(metric.model, "generate") as mock_generate:
        mock_generate.return_value = {
            "score": 7.5,
            "reason": "The output demonstrates good understanding and accuracy",
        }

        # Call evaluate method
        result = metric.evaluate(
            input="What is the capital of France?",
            output="Paris is the capital of France",
            expected_output="Paris",
            context=["France is a country in Europe"],
        )

        # Verify the result
        assert isinstance(result, MetricResult)
        assert result.score == 7.5
        assert result.details["score"] == 7.5
        assert (
            result.details["reason"]
            == "The output demonstrates good understanding and accuracy"
        )
        assert result.details["is_successful"] is True
        assert result.details["score_type"] == "numeric"
        assert result.details["min_score"] == 0.0
        assert result.details["max_score"] == 10.0
        assert result.details["threshold"] == 5.0
        assert (
            result.details["threshold_operator"]
            == ThresholdOperator.GREATER_THAN_OR_EQUAL.value
        )
        assert "prompt" in result.details

        # Verify model was called with correct parameters
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert "schema" in call_args.kwargs


def test_evaluate_error_handling(metric):
    """Test error handling when LLM evaluation fails."""
    # Set up metric parameters
    metric.min_score = 0.0
    metric.max_score = 10.0
    metric.threshold = 5.0
    metric.threshold_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL

    # Mock the model to raise an exception
    with patch.object(metric.model, "generate") as mock_generate:
        mock_generate.side_effect = Exception("LLM service unavailable")

        # Call evaluate method
        result = metric.evaluate(
            input="What is the capital of France?",
            output="Paris is the capital of France",
            expected_output="Paris",
            context=["France is a country in Europe"],
        )

        # Verify error handling
        assert isinstance(result, MetricResult)
        assert result.score == 0.0  # Default error score for numeric metrics
        assert result.details["is_successful"] is False
        assert result.details["score_type"] == "numeric"
        assert result.details["min_score"] == 0.0
        assert result.details["max_score"] == 10.0
        assert result.details["threshold"] == 5.0
        assert (
            result.details["threshold_operator"]
            == ThresholdOperator.GREATER_THAN_OR_EQUAL.value
        )
        assert "error" in result.details
        assert "exception_type" in result.details
        assert "exception_details" in result.details
        assert "prompt" in result.details


def test_from_config_to_config(metric):
    config1 = metric.to_config()
    metric2 = RhesisPromptMetricNumeric.from_config(config1)
    config2 = metric2.to_config()
    assert config1 == config2

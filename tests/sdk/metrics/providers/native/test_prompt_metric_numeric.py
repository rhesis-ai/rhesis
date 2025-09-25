import pytest
from rhesis.sdk.metrics.base import MetricType, ScoreType, ThresholdOperator
from rhesis.sdk.metrics.providers.native.prompt_metric_numeric import (
    RhesisPromptMetricNumeric,
)


@pytest.fixture
def metric(monkeypatch):
    monkeypatch.setenv("RHESIS_API_KEY", "test_api_key")
    return RhesisPromptMetricNumeric(
        name="test_metric",
        description="test_description",
        evaluation_prompt="test_prompt",
        evaluation_steps="test_steps",
        reasoning="test_reasoning",
        evaluation_examples="test_examples",
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


def test_validate_score_range(metric):
    metric._validate_score_range(1, 10)

    with pytest.raises(ValueError):
        metric._validate_score_range(1, None)
    with pytest.raises(ValueError):
        metric._validate_score_range(None, 1)
    with pytest.raises(ValueError):
        metric._validate_score_range(1, 1)

    with pytest.raises(ValueError):
        metric._validate_score_range(10, 1)


def test_set_score_parameters(metric):
    metric._set_score_parameters(1, 10, 5)
    assert metric.min_score == 1
    assert metric.max_score == 10
    assert metric.threshold == 5

    metric._set_score_parameters(1, 10, None)
    assert metric.min_score == 1
    assert metric.max_score == 10
    assert metric.threshold == 5.5

    with pytest.raises(ValueError):
        metric._set_score_parameters(1, 10, 11)


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
    metric.min_score = 1
    metric.max_score = 10
    metric.threshold = 5
    metric.threshold_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL
    config = metric.to_config()
    assert config.parameters == {
        "min_score": 1,
        "max_score": 10,
        "threshold": 5,
        "threshold_operator": ThresholdOperator.GREATER_THAN_OR_EQUAL,
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

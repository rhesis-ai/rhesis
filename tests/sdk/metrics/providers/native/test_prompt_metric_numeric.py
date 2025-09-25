import pytest
from rhesis.sdk.metrics.base import MetricType, ScoreType
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

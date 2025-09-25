import pytest
from rhesis.sdk.metrics.base import MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.prompt_metric_categorical import (
    RhesisPromptMetricCategorical,
)


@pytest.fixture
def metric(monkeypatch):
    monkeypatch.setenv("RHESIS_API_KEY", "test_api_key")
    return RhesisPromptMetricCategorical(
        name="test_metric",
        description="test_description",
        evaluation_prompt="test_prompt",
        evaluation_steps="test_steps",
        reasoning="test_reasoning",
        evaluation_examples="test_examples",
        categories=["test_category1", "test_category2"],
        passing_categories="test_category1",
    )


def test_prompt_metric_numeric_base__init__(metric):
    assert metric.evaluation_prompt == "test_prompt"
    assert metric.evaluation_steps == "test_steps"
    assert metric.reasoning == "test_reasoning"
    assert metric.evaluation_examples == "test_examples"
    assert metric.name == "test_metric"
    assert metric.description == "test_description"
    assert metric.metric_type == MetricType.RAG
    assert metric.score_type == ScoreType.CATEGORICAL


def test_validate_categories(metric):
    metric.categories = ["test_category1", "test_category2"]
    metric._validate_categories()

    with pytest.raises(ValueError):
        metric.categories = ["test_category1"]
        metric._validate_categories()


def test_validate_passing_categories(metric):
    metric.passing_categories = "test_category1"
    metric._validate_passing_categories()

    metric.passing_categories = ["test_category1", "test_category2"]
    metric._validate_passing_categories()

    with pytest.raises(ValueError):
        metric.passing_categories = 1
        metric._validate_passing_categories()


def test_normalize_passing_categories(metric):
    metric.passing_categories = "test_category1"
    metric._normalize_passing_categories()
    assert metric.passing_categories == ["test_category1"]


def test_validate_passing_categories_subset(metric):
    metric.categories = ["test_category1", "test_category2"]
    metric.passing_categories = ["test_category1"]
    metric._validate_passing_categories_subset()

    with pytest.raises(ValueError):
        metric.categories = ["test_category1", "test_category2"]
        metric.passing_categories = [
            "test_category1",
            "test_category2",
            "test_category3",
        ]
        metric._validate_passing_categories_subset()

    with pytest.raises(ValueError):
        metric.categories = ["test_category1", "test_category2"]
        metric.passing_categories = ["test_category3"]
        metric._validate_passing_categories_subset()


def test_evaluate_score(metric):
    assert metric._evaluate_score("test_category1", ["test_category1"]) is True
    assert metric._evaluate_score("test_category1", ["test_category2"]) is not True


def test_to_config(metric):
    assert metric.to_config().parameters == {
        "categories": ["test_category1", "test_category2"],
        "passing_categories": ["test_category1"],
    }

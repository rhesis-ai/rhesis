import pytest
from rhesis.sdk.metrics.base import MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.prompt_metric import RhesisPromptMetricBase
from rhesis.sdk.models.providers.gemini import GeminiLLM


@pytest.fixture
def metric(monkeypatch):
    monkeypatch.setenv("RHESIS_API_KEY", "test")
    return RhesisPromptMetricBase(
        name="test_metric",
        description="test_description",
        score_type="numeric",
        metric_type="rag",
    )


def test_prompt_metric_base__init__(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    metric = RhesisPromptMetricBase(
        name="test_metric",
        description="test_description",
        score_type="numeric",
        metric_type="rag",
        model=GeminiLLM(),
    )

    assert metric.name == "test_metric"
    assert metric.description == "test_description"
    assert metric.score_type == ScoreType.NUMERIC
    assert metric.metric_type == MetricType.RAG
    print(isinstance(metric.model, GeminiLLM))
    assert isinstance(metric.model, GeminiLLM)


def test_validate_evaluate_inputs(metric):
    metric._validate_evaluate_inputs("input", "output", "expected_output")
    metric._validate_evaluate_inputs("input", "output", "expected_output", ["context"])
    metric.requires_ground_truth = True

    with pytest.raises(ValueError):
        metric._validate_evaluate_inputs(1, "output", "expected_output")

    with pytest.raises(ValueError):
        metric._validate_evaluate_inputs("input", 1, "expected_output")

    with pytest.raises(ValueError):
        metric._validate_evaluate_inputs("input", "output", expected_output=None)

    with pytest.raises(ValueError):
        metric._validate_evaluate_inputs(
            "input", "output", expected_output=None, context=1
        )


def test_get_base_details(metric):
    metric.score_type = ScoreType.NUMERIC
    assert metric._get_base_details("test_prompt") == {
        "score_type": ScoreType.NUMERIC.value,
        "prompt": "test_prompt",
    }


def test_to_config(metric):
    metric.ground_truth_required = True
    metric.context_required = True

    config = metric.to_config()

    # Backend required items
    assert config.class_name == RhesisPromptMetricBase.__name__
    assert config.backend == "rhesis"
    assert config.name == metric.name
    assert config.description == metric.description
    assert config.score_type == metric.score_type
    assert config.metric_type == metric.metric_type
    assert config.ground_truth_required == metric.ground_truth_required
    assert config.context_required == metric.context_required
    # Custom parameters
    assert config.evaluation_prompt == metric.evaluation_prompt
    assert config.evaluation_steps == metric.evaluation_steps
    assert config.reasoning == metric.reasoning
    assert config.evaluation_examples == metric.evaluation_examples
    assert config.parameters == {}

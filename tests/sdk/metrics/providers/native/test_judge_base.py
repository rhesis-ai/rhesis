import pytest

from rhesis.sdk.metrics.base import MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.base import JudgeBase
from rhesis.sdk.metrics.providers.native.configs import BaseJudgeConfig
from rhesis.sdk.models.providers.gemini import GeminiLLM


@pytest.fixture
def config():
    config = BaseJudgeConfig(
        name="test_metric",
        description="test_description",
        score_type="numeric",
        metric_type="rag",
        requires_context=True,
        requires_ground_truth=True,
    )
    return config


@pytest.fixture
def metric(monkeypatch, config):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    return JudgeBase(config, model="gemini")


def test_prompt_metric_base__init__(monkeypatch, metric):
    monkeypatch.setenv("GEMINI_API_KEY", "test")

    assert metric.name == "test_metric"
    assert metric.description == "test_description"
    assert metric.score_type == ScoreType.NUMERIC
    assert metric.metric_type == MetricType.RAG
    assert isinstance(metric.model, GeminiLLM)


def test_validate_evaluate_inputs(metric):
    metric._validate_evaluate_inputs("input", "output", "expected_output")
    metric._validate_evaluate_inputs("input", "output", "expected_output", ["context"])

    assert hasattr(metric, "requires_ground_truth")

    with pytest.raises(ValueError):
        metric._validate_evaluate_inputs(1, "output", "expected_output")

    with pytest.raises(ValueError):
        metric._validate_evaluate_inputs("input", 1, "expected_output")

    with pytest.raises(ValueError):
        metric._validate_evaluate_inputs("input", "output", expected_output=None)

    # with pytest.raises(ValueError):
    #     metric._validate_evaluate_inputs(
    #         "input", "output", expected_output=None, context=1
    #     )


def test_get_base_details(metric):
    metric.score_type = ScoreType.NUMERIC
    assert metric._get_base_details("test_prompt") == {
        "score_type": ScoreType.NUMERIC.value,
        "prompt": "test_prompt",
    }

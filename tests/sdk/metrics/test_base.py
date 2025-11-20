import pytest
from rhesis.sdk.metrics.base import (
    Backend,
    BaseMetric,
    MetricConfig,
    MetricType,
    ScoreType,
)
from rhesis.sdk.models.providers.gemini import GeminiLLM
from rhesis.sdk.models.providers.native import RhesisLLM


def test_metric_config_defaults():
    config = MetricConfig()
    assert config.backend == Backend.RHESIS


def test_metric_config_with_backend():
    config = MetricConfig(backend="rhesis")
    assert config.backend == Backend.RHESIS
    config = MetricConfig(backend="deepeval")
    assert config.backend == Backend.DEEPEVAL


def test_metric_config_with_score_type():
    config = MetricConfig(score_type=ScoreType.NUMERIC)
    assert config.score_type == "numeric"
    config = MetricConfig(score_type="numeric")
    assert config.score_type == "numeric"


def test_metric_config_with_metric_type():
    config = MetricConfig(metric_type=MetricType.GENERATION)
    assert config.metric_type == "generation"
    config = MetricConfig(metric_type="generation")
    assert config.metric_type == "generation"


def test_metric_config_with_invalid_backend():
    with pytest.raises(ValueError):
        MetricConfig(backend="invalid")


def test_metric_config_with_invalid_score_type():
    with pytest.raises(ValueError):
        MetricConfig(score_type="invalid")


def test_metric_config_with_invalid_metric_type():
    with pytest.raises(ValueError):
        MetricConfig(metric_type="invalid")


def test_base_metric_init():
    class TestMetric(BaseMetric):
        def evaluate(self):
            pass

    config = MetricConfig(
        name="test",
        description="test description",
        score_type="numeric",
        metric_type="generation",
    )
    metric = TestMetric(config)
    assert metric.name == "test"
    assert metric.description == "test description"
    assert metric.score_type == ScoreType.NUMERIC
    assert metric.metric_type == MetricType.GENERATION


def test_base_set_model():
    class TestMetric(BaseMetric):
        def evaluate(self):
            pass

    config = MetricConfig(
        name="test",
        description="test description",
        score_type="numeric",
        metric_type="generation",
    )
    metric = TestMetric(config)
    # Test default model
    model = metric.set_model(None)
    assert isinstance(model, RhesisLLM)

    model = metric.set_model("gemini")
    assert isinstance(model, GeminiLLM)

    model = metric.set_model(GeminiLLM())
    assert isinstance(model, GeminiLLM)


def test_base_metric_model_in_init():
    class TestMetric(BaseMetric):
        def evaluate(self):
            pass

    config = MetricConfig(
        name="test",
        description="test description",
        score_type="numeric",
        metric_type="generation",
    )
    metric = TestMetric(config, model=None)
    assert isinstance(metric.model, RhesisLLM)
    metric = TestMetric(config, model="gemini")
    assert isinstance(metric.model, GeminiLLM)
    metric = TestMetric(config, model=GeminiLLM())
    assert isinstance(metric.model, GeminiLLM)

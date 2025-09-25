from rhesis.sdk.metrics.base import MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.prompt_metric import RhesisPromptMetricBase
from rhesis.sdk.models.providers.gemini import GeminiLLM


def test_prompt_metric_base__init__():
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

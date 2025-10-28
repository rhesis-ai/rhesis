import pytest

from rhesis.sdk.metrics.config.loader import MetricConfigLoader
from rhesis.sdk.metrics.factory import MetricFactory


@pytest.fixture
def evaluator():
    from rhesis.sdk.metrics.evaluator import MetricEvaluator

    return MetricEvaluator()


@pytest.fixture
def config():
    return MetricConfigLoader()


@pytest.fixture
def sample_data():
    return {
        "input_text": "What is the capital of France?",
        "output_text": "The capital of France is Paris. It is known as the City of Light.",
        "expected_output": "Paris is the capital of France.",
        "context": [
            "Paris is the capital and largest city of France.",
            "Known as the City of Light, Paris is a global center for art, culture, and fashion.",
        ],
    }


@pytest.fixture
def all_metric_types():
    factory = MetricFactory()
    return factory.get_factory("deepeval").list_supported_metrics()


def test_evaluator_interface(evaluator):
    """Test that evaluator has the correct interface."""
    assert hasattr(evaluator, "evaluate")
    assert callable(evaluator.evaluate)


def test_metric_result_interface(evaluator, sample_data):
    """Test that metric results conform to the expected format."""
    results = evaluator.evaluate(
        metrics=[
            {"class_name": "DeepEvalAnswerRelevancy", "backend": "deepeval", "threshold": 0.7}
        ],
        **sample_data,
    )

    for metric_name, result in results.items():
        assert "score" in result
        assert "reason" in result
        assert "is_successful" in result
        assert "threshold" in result
        assert "backend" in result
        assert "description" in result

        assert isinstance(result["score"], float)
        assert 0 <= result["score"] <= 1
        assert isinstance(result["is_successful"], bool)
        assert isinstance(result["threshold"], float)
        assert isinstance(result["reason"], str)
        assert isinstance(result["description"], str)


def test_specific_metrics(evaluator, sample_data):
    """Test evaluation with specific metrics."""
    metrics = [
        {
            "class_name": "DeepEvalAnswerRelevancy",
            "backend": "deepeval",
            "threshold": 0.7,
            "description": "Measures how relevant the answer is to the question",
        },
        {
            "class_name": "DeepEvalFaithfulness",
            "backend": "deepeval",
            "threshold": 0.8,
            "description": "Measures how faithful the answer is to the context",
        },
    ]
    results = evaluator.evaluate(metrics=metrics, **sample_data)

    assert set(results.keys()) == {"DeepEvalAnswerRelevancy", "DeepEvalFaithfulness"}
    # Check that thresholds were applied correctly
    assert results["DeepEvalAnswerRelevancy"]["threshold"] == 0.7
    assert results["DeepEvalFaithfulness"]["threshold"] == 0.8


def test_invalid_metric(evaluator, sample_data):
    """Test that invalid metrics are handled properly."""
    # The evaluator logs errors but returns empty results when metrics are invalid
    results = evaluator.evaluate(
        metrics=[{"class_name": "InvalidMetric", "backend": "deepeval"}], **sample_data
    )

    # Should return empty results since the metric is invalid
    assert results == {}


def test_missing_required_params(evaluator):
    """Test that missing required parameters raise appropriate errors."""
    with pytest.raises(TypeError):
        evaluator.evaluate()


def test_config_loading(config):
    """Test that configuration is loaded correctly."""
    assert "backends" in config._config
    assert "deepeval" in config.backends
    assert "module" in config.backends["deepeval"]
    assert "factory" in config.backends["deepeval"]


if __name__ == "__main__":
    pytest.main([__file__])

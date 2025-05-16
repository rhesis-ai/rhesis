import pytest

from .config.loader import MetricConfigLoader
from .factory import MetricFactory


@pytest.fixture
def evaluator():
    from .evaluator import MetricEvaluator

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
    factory = MetricFactory.get_factory("deepeval")
    return factory.list_supported_metrics()


def test_evaluator_interface(evaluator):
    """Test that evaluator has the correct interface."""
    assert hasattr(evaluator, "evaluate")
    assert callable(evaluator.evaluate)


def test_metric_result_interface(evaluator, sample_data):
    """Test that metric results conform to the expected format."""
    results = evaluator.evaluate(**sample_data)

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


def test_specific_metrics(evaluator, sample_data, config):
    """Test evaluation with specific metrics."""
    metrics = [
        {"name": "answer_relevancy", "threshold": 0.7},
        {"name": "faithfulness", "threshold": 0.8},
    ]
    results = evaluator.evaluate(metrics=metrics, **sample_data)

    assert set(results.keys()) == set(m["name"] for m in metrics)
    # Check that thresholds were applied correctly
    assert results["answer_relevancy"]["threshold"] == 0.7
    assert results["faithfulness"]["threshold"] == 0.8


def test_invalid_metric(evaluator, sample_data):
    """Test that invalid metrics raise appropriate errors."""
    with pytest.raises(ValueError):
        evaluator.evaluate(metrics=[{"name": "invalid_metric"}], **sample_data)


def test_missing_required_params(evaluator):
    """Test that missing required parameters raise appropriate errors."""
    with pytest.raises(TypeError):
        evaluator.evaluate()


def test_config_loading(config):
    """Test that configuration is loaded correctly."""
    assert "metrics" in config._config
    assert "backends" in config._config
    assert "deepeval" in config.backends
    assert "answer_relevancy" in config.metrics


if __name__ == "__main__":
    pytest.main([__file__])

import pytest

from rhesis.sdk.metrics.providers.ragas import RagasAnswerRelevancy, RagasContextualPrecision


@pytest.fixture
def sample_data():
    return {
        "input": "What is the capital of France?",
        "output": "The capital of France is Paris. It is known as the City of Light.",
        "expected_output": "Paris is the capital of France.",
        "context": [
            "Paris is the capital and largest city of France.",
            "Known as the City of Light, Paris is a global center for art, culture, and fashion.",
        ],
    }


def test_ragas_answer_relevancy_init():
    """Test initialization of RagasAnswerRelevancy."""
    metric = RagasAnswerRelevancy(threshold=0.7)
    assert metric.name == "answer_relevancy"
    assert metric.threshold == 0.7
    assert metric.requires_ground_truth is True


def test_ragas_contextual_precision_init():
    """Test initialization of RagasContextualPrecision."""
    metric = RagasContextualPrecision(threshold=0.6)
    assert metric.name == "contextual_precision"
    assert metric.threshold == 0.6
    assert metric.requires_ground_truth is False


def test_ragas_metric_evaluate_placeholder(sample_data):
    """Test evaluate method with placeholder implementation."""
    metric = RagasAnswerRelevancy()
    result = metric.evaluate(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"],
    )

    # Since this is a placeholder, we just check the structure
    assert result.score == 0.0
    assert "reason" in result.details
    assert "is_successful" in result.details
    assert result.details["is_successful"] is False
    assert "threshold" in result.details


def test_metric_threshold_validation():
    """Test threshold validation."""
    with pytest.raises(ValueError):
        RagasAnswerRelevancy(threshold=-0.1)

    with pytest.raises(ValueError):
        RagasAnswerRelevancy(threshold=1.1)


if __name__ == "__main__":
    pytest.main([__file__])

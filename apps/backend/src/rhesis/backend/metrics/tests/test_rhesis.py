import pytest
from unittest.mock import patch, MagicMock

from rhesis.backend.metrics.rhesis import (
    RhesisPromptMetric, 
    ScoreResponse
)


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


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response for testing."""
    mock_response = MagicMock()
    mock_response.score = 4.5
    mock_response.reason = "The response is accurate and comprehensive"
    mock_response._response = MagicMock()
    mock_response._response.content = '{"score": 4.5, "reason": "The response is accurate and comprehensive"}'
    return mock_response


def test_rhesis_prompt_metric_init():
    """Test initialization of RhesisPromptMetric."""
    metric = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Test prompt",
        evaluation_steps="Test steps",
        reasoning="Test reasoning",
        min_score=1.0,
        max_score=5.0,
        threshold=0.6,
        provider="openai",
        model="gpt-4o"
    )
    
    assert metric.name == "test_metric"
    assert metric.evaluation_prompt == "Test prompt"
    assert metric.evaluation_steps == "Test steps"
    assert metric.reasoning == "Test reasoning"
    assert metric.min_score == 1.0
    assert metric.max_score == 5.0
    assert metric.threshold == 0.6
    assert metric.provider == "openai"
    assert metric.model == "gpt-4o"
    assert metric.requires_ground_truth is True


@patch("mirascope.llm.override")
def test_rhesis_prompt_metric_evaluate(mock_override, mock_llm_response, sample_data):
    """Test evaluation using RhesisPromptMetric."""
    # Configure the mock to return our mock response
    mock_eval_fn = MagicMock()
    mock_eval_fn.return_value = mock_llm_response
    mock_override.return_value = mock_eval_fn

    metric = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Test prompt",
        evaluation_steps="Test steps",
        reasoning="Test reasoning",
        min_score=1.0,
        max_score=5.0,
        threshold=0.6
    )
    
    result = metric.evaluate(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"]
    )
    
    # Verify result
    assert isinstance(result.score, float)
    assert 0 <= result.score <= 1  # Score should be normalized
    assert "raw_score" in result.details
    assert result.details["raw_score"] == 4.5  # The mock value
    assert "reason" in result.details
    assert "is_successful" in result.details
    assert "threshold" in result.details
    assert result.details["threshold"] == 0.6


def test_rhesis_prompt_metric_get_prompt_template(sample_data):
    """Test the prompt template generation."""
    metric = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Rate the answer quality",
        evaluation_steps="Read and analyze",
        reasoning="Consider accuracy",
        min_score=1.0,
        max_score=5.0
    )
    
    prompt = metric.get_prompt_template(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"]
    )
    
    # Verify the prompt contains all expected content
    assert "Rate the answer quality" in prompt
    assert "Read and analyze" in prompt
    assert "Consider accuracy" in prompt
    assert sample_data["input"] in prompt
    assert sample_data["output"] in prompt
    assert sample_data["expected_output"] in prompt
    assert any(context in prompt for context in sample_data["context"])
    assert "1.0" in prompt and "5.0" in prompt  # Min and max scores


def test_rhesis_metric_threshold_validation():
    """Test that threshold validation works correctly."""
    # Test 1: Invalid threshold (above max_score)
    with pytest.raises(ValueError):
        RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Test prompt",
            evaluation_steps="Test steps",
            reasoning="Test reasoning",
            min_score=1.0,
            max_score=5.0,
            threshold=6.0  # Invalid: higher than max_score
        )
        
    # Test 2: Invalid threshold (below min_score and not between 0-1)
    with pytest.raises(ValueError):
        RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Test prompt",
            evaluation_steps="Test steps",
            reasoning="Test reasoning",
            min_score=1.0,
            max_score=5.0,
            threshold=-0.5  # Invalid: lower than min_score and not a normalized value
        )
    
    # Test 3: Valid normalized threshold (between 0-1)
    metric1 = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Test prompt",
        evaluation_steps="Test steps",
        reasoning="Test reasoning",
        min_score=1.0,
        max_score=5.0,
        threshold=0.7  # Valid normalized threshold
    )
    assert metric1.threshold == 0.7
    
    # Test 4: Valid raw threshold (between min_score and max_score)
    metric2 = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Test prompt",
        evaluation_steps="Test steps",
        reasoning="Test reasoning",
        min_score=1.0,
        max_score=5.0,
        threshold=3.0  # Valid raw threshold (will be normalized)
    )
    assert metric2.threshold == 0.5  # (3.0 - 1.0) / (5.0 - 1.0) = 0.5


if __name__ == "__main__":
    pytest.main([__file__]) 
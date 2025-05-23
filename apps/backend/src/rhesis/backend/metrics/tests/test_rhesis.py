import pytest
from unittest.mock import patch, MagicMock

from rhesis.backend.metrics.rhesis import (
    RhesisPromptMetric, 
    RhesisDetailedPromptMetric, 
    ScoreResponse,
    DetailedScoreResponse
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


@pytest.fixture
def mock_detailed_llm_response():
    """Create a mock LLM detailed response for testing."""
    mock_response = MagicMock()
    mock_response.overall_score = 4.2
    mock_response.relevance_score = 4.5
    mock_response.accuracy_score = 4.0
    mock_response.coherence_score = 4.3
    mock_response.reasoning = "The response addresses the query with accurate information in a coherent way"
    mock_response._response = MagicMock()
    mock_response._response.content = """
    {
        "overall_score": 4.2,
        "relevance_score": 4.5,
        "accuracy_score": 4.0,
        "coherence_score": 4.3,
        "reasoning": "The response addresses the query with accurate information in a coherent way"
    }
    """
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


@patch("mirascope.llm.override")
def test_rhesis_detailed_prompt_metric_evaluate(mock_override, mock_detailed_llm_response, sample_data):
    """Test evaluation using RhesisDetailedPromptMetric."""
    # Configure the mock to return our mock response
    mock_eval_fn = MagicMock()
    mock_eval_fn.return_value = mock_detailed_llm_response
    mock_override.return_value = mock_eval_fn

    metric = RhesisDetailedPromptMetric(
        name="test_detailed_metric",
        evaluation_prompt="Test detailed prompt",
        evaluation_steps="Test detailed steps",
        reasoning="Test detailed reasoning",
        min_score=1.0,
        max_score=5.0,
        threshold=0.7
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
    assert result.details["raw_score"] == 4.2  # The mock overall_score
    assert "relevance_score" in result.details
    assert result.details["relevance_score"] == 4.5
    assert "accuracy_score" in result.details
    assert result.details["accuracy_score"] == 4.0
    assert "coherence_score" in result.details
    assert result.details["coherence_score"] == 4.3
    assert "reasoning" in result.details
    assert "is_successful" in result.details
    assert "threshold" in result.details
    assert result.details["threshold"] == 0.7


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
    """Test that threshold validation works."""
    with pytest.raises(ValueError):
        RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Test prompt",
            evaluation_steps="Test steps",
            reasoning="Test reasoning",
            threshold=1.5  # Invalid threshold > 1
        )
        
    with pytest.raises(ValueError):
        RhesisPromptMetric(
            name="test_metric",
            evaluation_prompt="Test prompt",
            evaluation_steps="Test steps",
            reasoning="Test reasoning",
            threshold=-0.5  # Invalid threshold < 0
        )


if __name__ == "__main__":
    pytest.main([__file__]) 
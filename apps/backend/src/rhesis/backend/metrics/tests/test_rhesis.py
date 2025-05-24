import pytest
from unittest.mock import patch, MagicMock
from typing import Optional, List

from rhesis.backend.metrics.rhesis import (
    RhesisPromptMetric, 
    ScoreResponse
)
from rhesis.backend.metrics.rhesis.metric_base import (
    RhesisMetricBase,
    ScoreType,
    ThresholdOperator
)
from rhesis.backend.metrics.base import MetricResult


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
def mock_binary_response():
    """Create a mock binary LLM response for testing."""
    mock_response = MagicMock()
    mock_response.score = True
    mock_response.reason = "The response meets the criteria"
    mock_response._response = MagicMock()
    mock_response._response.content = '{"score": true, "reason": "The response meets the criteria"}'
    return mock_response


@pytest.fixture
def mock_categorical_response():
    """Create a mock categorical LLM response for testing."""
    mock_response = MagicMock()
    mock_response.score = "excellent"
    mock_response.reason = "The response demonstrates high quality"
    mock_response._response = MagicMock()
    mock_response._response.content = '{"score": "excellent", "reason": "The response demonstrates high quality"}'
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


def test_rhesis_prompt_metric_init_with_score_types():
    """Test initialization with different score types."""
    # Test numeric score type
    numeric_metric = RhesisPromptMetric(
        name="numeric_metric",
        evaluation_prompt="Rate numerically",
        evaluation_steps="Steps",
        reasoning="Reasoning",
        score_type=ScoreType.NUMERIC,
        threshold_operator=ThresholdOperator.GREATER_THAN_OR_EQUAL
    )
    assert numeric_metric.score_type == ScoreType.NUMERIC
    assert numeric_metric.threshold_operator == ThresholdOperator.GREATER_THAN_OR_EQUAL
    
    # Test binary score type
    binary_metric = RhesisPromptMetric(
        name="binary_metric",
        evaluation_prompt="Rate true/false",
        evaluation_steps="Steps",
        reasoning="Reasoning",
        score_type="binary",  # Test string input
        threshold=1.0,
        threshold_operator="="  # Test string input
    )
    assert binary_metric.score_type == ScoreType.BINARY
    assert binary_metric.threshold_operator == ThresholdOperator.EQUAL
    
    # Test categorical score type
    categorical_metric = RhesisPromptMetric(
        name="categorical_metric",
        evaluation_prompt="Rate categorically",
        evaluation_steps="Steps",
        reasoning="Reasoning",
        score_type=ScoreType.CATEGORICAL,
        threshold="good"
    )
    assert categorical_metric.score_type == ScoreType.CATEGORICAL


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
def test_rhesis_prompt_metric_evaluate_binary(mock_override, mock_binary_response, sample_data):
    """Test evaluation with binary score type."""
    mock_eval_fn = MagicMock()
    mock_eval_fn.return_value = mock_binary_response
    mock_override.return_value = mock_eval_fn

    metric = RhesisPromptMetric(
        name="binary_metric",
        evaluation_prompt="Is this correct?",
        evaluation_steps="Check accuracy",
        reasoning="Binary evaluation",
        score_type=ScoreType.BINARY,
        threshold=1.0,
        threshold_operator=ThresholdOperator.EQUAL
    )
    
    result = metric.evaluate(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"]
    )
    
    # Verify binary result
    assert result.score == 1.0  # Should be converted to 1.0 for True
    assert result.details["raw_score"] is True
    assert result.details["processed_score"] == 1.0
    assert result.details["score_type"] == "binary"
    assert result.details["is_successful"] is True


@patch("mirascope.llm.override")
def test_rhesis_prompt_metric_evaluate_categorical(mock_override, mock_categorical_response, sample_data):
    """Test evaluation with categorical score type."""
    mock_eval_fn = MagicMock()
    mock_eval_fn.return_value = mock_categorical_response
    mock_override.return_value = mock_eval_fn

    metric = RhesisPromptMetric(
        name="categorical_metric",
        evaluation_prompt="Rate quality level",
        evaluation_steps="Assess overall quality",
        reasoning="Categorical evaluation",
        score_type=ScoreType.CATEGORICAL,
        threshold="excellent",
        threshold_operator=ThresholdOperator.EQUAL
    )
    
    result = metric.evaluate(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"]
    )
    
    # Verify categorical result
    assert result.score == "excellent"
    assert result.details["raw_score"] == "excellent"
    assert result.details["processed_score"] == "excellent"
    assert result.details["score_type"] == "categorical"
    assert result.details["is_successful"] is True


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


def test_score_processing():
    """Test score processing for different score types."""
    metric = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Test",
        evaluation_steps="Test",
        reasoning="Test",
        score_type=ScoreType.BINARY
    )
    
    # Test binary score processing
    assert metric._process_score("true") == 1.0
    assert metric._process_score("false") == 0.0
    assert metric._process_score("yes") == 1.0
    assert metric._process_score("no") == 0.0
    assert metric._process_score("1") == 1.0
    assert metric._process_score("0") == 0.0
    assert metric._process_score(1) == 1.0
    assert metric._process_score(0) == 0.0
    
    # Test numeric score processing
    numeric_metric = RhesisPromptMetric(
        name="numeric_test",
        evaluation_prompt="Test",
        evaluation_steps="Test",
        reasoning="Test",
        score_type=ScoreType.NUMERIC,
        min_score=1.0,
        max_score=5.0
    )
    
    assert numeric_metric._process_score(3.5) == 3.5
    assert numeric_metric._process_score(0.5) == 1.0  # Clamped to min
    assert numeric_metric._process_score(6.0) == 5.0  # Clamped to max
    assert numeric_metric._process_score("3.0") == 3.0
    
    # Test categorical score processing
    categorical_metric = RhesisPromptMetric(
        name="categorical_test",
        evaluation_prompt="Test",
        evaluation_steps="Test",
        reasoning="Test",
        score_type=ScoreType.CATEGORICAL
    )
    
    assert categorical_metric._process_score("excellent") == "excellent"
    assert categorical_metric._process_score(5) == 5.0


class TestableRhesisMetricBase(RhesisMetricBase):
    """Concrete implementation of RhesisMetricBase for testing purposes."""
    
    @property
    def requires_ground_truth(self) -> bool:
        return False
    
    def evaluate(self, input: str, output: str, expected_output: Optional[str], context: List[str] = None) -> MetricResult:
        # Simple mock implementation for testing
        return MetricResult(score=0.5, details={"test": "value"})


class TestRhesisMetricBase:
    """Test cases for the base metric class functionality."""
    
    def test_threshold_operator_sanitization(self):
        """Test threshold operator sanitization."""
        base = TestableRhesisMetricBase("test")
        
        # Test valid operators
        assert base._sanitize_threshold_operator(">=") == ThresholdOperator.GREATER_THAN_OR_EQUAL
        assert base._sanitize_threshold_operator(" <= ") == ThresholdOperator.LESS_THAN_OR_EQUAL  # With whitespace
        assert base._sanitize_threshold_operator(ThresholdOperator.EQUAL) == ThresholdOperator.EQUAL
        
        # Test invalid operators
        with pytest.raises(ValueError, match="Invalid threshold operator"):
            base._sanitize_threshold_operator(">>")
        
        with pytest.raises(ValueError, match="Invalid threshold operator"):
            base._sanitize_threshold_operator("unknown")
    
    def test_operator_validation_for_score_types(self):
        """Test that operators are validated for appropriate score types."""
        base = TestableRhesisMetricBase("test")
        
        # Valid combinations
        base._validate_operator_for_score_type(ThresholdOperator.EQUAL, ScoreType.BINARY)
        base._validate_operator_for_score_type(ThresholdOperator.NOT_EQUAL, ScoreType.BINARY)
        base._validate_operator_for_score_type(ThresholdOperator.EQUAL, ScoreType.CATEGORICAL)
        base._validate_operator_for_score_type(ThresholdOperator.GREATER_THAN, ScoreType.NUMERIC)
        
        # Invalid combinations
        with pytest.raises(ValueError, match="not valid for score type"):
            base._validate_operator_for_score_type(ThresholdOperator.GREATER_THAN, ScoreType.BINARY)
        
        with pytest.raises(ValueError, match="not valid for score type"):
            base._validate_operator_for_score_type(ThresholdOperator.LESS_THAN, ScoreType.CATEGORICAL)
    
    def test_evaluate_score_numeric(self):
        """Test score evaluation for numeric score types."""
        base = TestableRhesisMetricBase("test", threshold=0.7)
        
        # Test different operators with numeric scores
        assert base.evaluate_score(0.8, ScoreType.NUMERIC, 0.7, ThresholdOperator.GREATER_THAN_OR_EQUAL) is True
        assert base.evaluate_score(0.6, ScoreType.NUMERIC, 0.7, ThresholdOperator.GREATER_THAN_OR_EQUAL) is False
        assert base.evaluate_score(0.6, ScoreType.NUMERIC, 0.7, ThresholdOperator.LESS_THAN) is True
        assert base.evaluate_score(0.8, ScoreType.NUMERIC, 0.7, ThresholdOperator.LESS_THAN) is False
        assert base.evaluate_score(0.7, ScoreType.NUMERIC, 0.7, ThresholdOperator.EQUAL) is True
        assert base.evaluate_score(0.8, ScoreType.NUMERIC, 0.7, ThresholdOperator.EQUAL) is False
        assert base.evaluate_score(0.8, ScoreType.NUMERIC, 0.7, ThresholdOperator.NOT_EQUAL) is True
        assert base.evaluate_score(0.7, ScoreType.NUMERIC, 0.7, ThresholdOperator.NOT_EQUAL) is False
    
    def test_evaluate_score_binary(self):
        """Test score evaluation for binary score types."""
        base = TestableRhesisMetricBase("test")
        
        # Test binary evaluation (only = and != should work)
        assert base.evaluate_score(1.0, ScoreType.BINARY, 1.0, ThresholdOperator.EQUAL) is True
        assert base.evaluate_score(0.0, ScoreType.BINARY, 1.0, ThresholdOperator.EQUAL) is False
        assert base.evaluate_score(0.0, ScoreType.BINARY, 1.0, ThresholdOperator.NOT_EQUAL) is True
        assert base.evaluate_score(1.0, ScoreType.BINARY, 1.0, ThresholdOperator.NOT_EQUAL) is False
    
    def test_evaluate_score_categorical(self):
        """Test score evaluation for categorical score types."""
        base = TestableRhesisMetricBase("test")
        
        # Test categorical evaluation
        assert base.evaluate_score("excellent", ScoreType.CATEGORICAL, "excellent", ThresholdOperator.EQUAL) is True
        assert base.evaluate_score("good", ScoreType.CATEGORICAL, "excellent", ThresholdOperator.EQUAL) is False
        assert base.evaluate_score("good", ScoreType.CATEGORICAL, "excellent", ThresholdOperator.NOT_EQUAL) is True
        assert base.evaluate_score("excellent", ScoreType.CATEGORICAL, "excellent", ThresholdOperator.NOT_EQUAL) is False
    
    def test_evaluate_score_defaults(self):
        """Test that default operators are set correctly based on score type."""
        base = TestableRhesisMetricBase("test", threshold=0.7)
        
        # Default for numeric should be >=
        assert base.evaluate_score(0.8, ScoreType.NUMERIC, None, None) is True  # 0.8 >= 0.7
        assert base.evaluate_score(0.6, ScoreType.NUMERIC, None, None) is False  # 0.6 < 0.7
        
        # Default for binary should be =
        assert base.evaluate_score(1.0, ScoreType.BINARY, 1.0, None) is True
        assert base.evaluate_score(0.0, ScoreType.BINARY, 1.0, None) is False
        
        # Default for categorical should be =
        assert base.evaluate_score("test", ScoreType.CATEGORICAL, "test", None) is True
        assert base.evaluate_score("other", ScoreType.CATEGORICAL, "test", None) is False


if __name__ == "__main__":
    pytest.main([__file__]) 
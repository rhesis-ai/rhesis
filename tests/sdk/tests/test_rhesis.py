from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.providers.native import (
    RhesisMetricBase,
    RhesisPromptMetric,
    ScoreType,
    ThresholdOperator,
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
    mock_response._response.content = (
        '{"score": 4.5, "reason": "The response is accurate and comprehensive"}'
    )
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
    mock_response._response.content = (
        '{"score": "excellent", "reason": "The response demonstrates high quality"}'
    )
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
        model="gpt-4o",
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
        threshold_operator=ThresholdOperator.GREATER_THAN_OR_EQUAL,
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
        reference_score="true",
        threshold_operator="=",  # Test string input
    )
    assert binary_metric.score_type == ScoreType.BINARY
    assert binary_metric.threshold_operator == ThresholdOperator.EQUAL
    assert binary_metric.reference_score == "true"
    assert binary_metric.threshold is None
    assert binary_metric.min_score is None
    assert binary_metric.max_score is None

    # Test categorical score type
    categorical_metric = RhesisPromptMetric(
        name="categorical_metric",
        evaluation_prompt="Rate categorically",
        evaluation_steps="Steps",
        reasoning="Reasoning",
        score_type=ScoreType.CATEGORICAL,
        reference_score="excellent",
    )
    assert categorical_metric.score_type == ScoreType.CATEGORICAL
    assert categorical_metric.reference_score == "excellent"
    assert categorical_metric.threshold is None
    assert categorical_metric.min_score is None
    assert categorical_metric.max_score is None


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
        threshold=0.6,
    )

    result = metric.evaluate(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"],
    )

    # Verify result
    assert isinstance(result.score, float)
    assert result.score == 4.5  # Score should be raw, not normalized
    assert "raw_score" in result.details
    assert result.details["raw_score"] == 4.5  # The mock value
    assert "reason" in result.details
    assert "is_successful" in result.details
    assert "threshold" in result.details


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
        reference_score="true",
        threshold_operator=ThresholdOperator.EQUAL,
    )

    result = metric.evaluate(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"],
    )

    # Verify binary result
    assert result.score == "true"  # Should be string "true" for binary
    assert result.details["raw_score"] is True
    assert result.details["processed_score"] == "true"
    assert result.details["score_type"] == "binary"
    assert result.details["is_successful"] is True
    assert result.details["reference_score"] == "true"
    assert "threshold" not in result.details  # No threshold for binary


@patch("mirascope.llm.override")
def test_rhesis_prompt_metric_evaluate_categorical(
    mock_override, mock_categorical_response, sample_data
):
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
        reference_score="excellent",
        threshold_operator=ThresholdOperator.EQUAL,
    )

    result = metric.evaluate(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"],
    )

    # Verify categorical result
    assert result.score == "excellent"
    assert result.details["raw_score"] == "excellent"
    assert result.details["processed_score"] == "excellent"
    assert result.details["score_type"] == "categorical"
    assert result.details["is_successful"] is True
    assert result.details["reference_score"] == "excellent"
    assert "threshold" not in result.details  # No threshold for categorical


def test_rhesis_prompt_metric_get_prompt_template(sample_data):
    """Test the prompt template generation."""
    metric = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Rate the answer quality",
        evaluation_steps="Read and analyze",
        reasoning="Consider accuracy",
        min_score=1.0,
        max_score=5.0,
    )

    prompt = metric.get_prompt_template(
        input=sample_data["input"],
        output=sample_data["output"],
        expected_output=sample_data["expected_output"],
        context=sample_data["context"],
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
            threshold=6.0,  # Invalid: higher than max_score
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
            threshold=-0.5,  # Invalid: lower than min_score and not a normalized value
        )

    # Test 3: Valid normalized threshold (between 0-1)
    metric1 = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Test prompt",
        evaluation_steps="Test steps",
        reasoning="Test reasoning",
        min_score=1.0,
        max_score=5.0,
        threshold=0.7,  # Valid normalized threshold
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
        threshold=3.0,  # Valid raw threshold (will be normalized)
    )
    assert metric2.threshold == 0.5  # (3.0 - 1.0) / (5.0 - 1.0) = 0.5


def test_score_processing():
    """Test score processing for different score types."""
    metric = RhesisPromptMetric(
        name="test_metric",
        evaluation_prompt="Test",
        evaluation_steps="Test",
        reasoning="Test",
        score_type=ScoreType.BINARY,
    )

    # Test binary score processing
    assert metric._process_score("true") == "true"
    assert metric._process_score("false") == "false"
    assert metric._process_score("yes") == "true"
    assert metric._process_score("no") == "false"
    assert metric._process_score("1") == "true"
    assert metric._process_score("0") == "false"
    assert metric._process_score(1) == "true"
    assert metric._process_score(0) == "false"
    assert metric._process_score(True) == "true"
    assert metric._process_score(False) == "false"

    # Test numeric score processing
    numeric_metric = RhesisPromptMetric(
        name="numeric_test",
        evaluation_prompt="Test",
        evaluation_steps="Test",
        reasoning="Test",
        score_type=ScoreType.NUMERIC,
        min_score=1.0,
        max_score=5.0,
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
        score_type=ScoreType.CATEGORICAL,
        reference_score="excellent",
    )

    assert categorical_metric._process_score("excellent") == "excellent"
    assert categorical_metric._process_score(5) == "5"
    assert categorical_metric._process_score("good") == "good"


class MockRhesisMetricBase(RhesisMetricBase):
    """Concrete implementation of RhesisMetricBase for testing purposes."""

    @property
    def requires_ground_truth(self) -> bool:
        return False

    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str] = None
    ) -> MetricResult:
        # Simple mock implementation for testing
        return MetricResult(score=0.5, details={"test": "value"})


class TestRhesisMetricBase:
    """Test cases for the base metric class functionality."""

    def test_threshold_operator_sanitization(self):
        """Test threshold operator sanitization."""
        base = MockRhesisMetricBase("test")

        # Test valid operators
        assert base._sanitize_threshold_operator(">=") == ThresholdOperator.GREATER_THAN_OR_EQUAL
        assert (
            base._sanitize_threshold_operator(" <= ") == ThresholdOperator.LESS_THAN_OR_EQUAL
        )  # With whitespace
        assert base._sanitize_threshold_operator(ThresholdOperator.EQUAL) == ThresholdOperator.EQUAL

        # Test invalid operators
        with pytest.raises(ValueError, match="Invalid threshold operator"):
            base._sanitize_threshold_operator(">>")

        with pytest.raises(ValueError, match="Invalid threshold operator"):
            base._sanitize_threshold_operator("unknown")

    def test_operator_validation_for_score_types(self):
        """Test that operators are validated for appropriate score types."""
        base = MockRhesisMetricBase("test")

        # Valid combinations
        base._validate_operator_for_score_type(ThresholdOperator.EQUAL, ScoreType.BINARY)
        base._validate_operator_for_score_type(ThresholdOperator.NOT_EQUAL, ScoreType.BINARY)
        base._validate_operator_for_score_type(ThresholdOperator.EQUAL, ScoreType.CATEGORICAL)
        base._validate_operator_for_score_type(ThresholdOperator.GREATER_THAN, ScoreType.NUMERIC)

        # Invalid combinations
        with pytest.raises(ValueError, match="not valid for score type"):
            base._validate_operator_for_score_type(ThresholdOperator.GREATER_THAN, ScoreType.BINARY)

        with pytest.raises(ValueError, match="not valid for score type"):
            base._validate_operator_for_score_type(
                ThresholdOperator.LESS_THAN, ScoreType.CATEGORICAL
            )

    def test_evaluate_score_numeric(self):
        """Test score evaluation for numeric score types."""
        base = MockRhesisMetricBase("test", threshold=0.7)

        # Test different operators with numeric scores
        assert (
            base.evaluate_score(
                0.8,
                ScoreType.NUMERIC,
                threshold=0.7,
                threshold_operator=ThresholdOperator.GREATER_THAN_OR_EQUAL,
            )
            is True
        )
        assert (
            base.evaluate_score(
                0.6,
                ScoreType.NUMERIC,
                threshold=0.7,
                threshold_operator=ThresholdOperator.GREATER_THAN_OR_EQUAL,
            )
            is False
        )
        assert (
            base.evaluate_score(
                0.6,
                ScoreType.NUMERIC,
                threshold=0.7,
                threshold_operator=ThresholdOperator.LESS_THAN,
            )
            is True
        )
        assert (
            base.evaluate_score(
                0.8,
                ScoreType.NUMERIC,
                threshold=0.7,
                threshold_operator=ThresholdOperator.LESS_THAN,
            )
            is False
        )
        assert (
            base.evaluate_score(
                0.7, ScoreType.NUMERIC, threshold=0.7, threshold_operator=ThresholdOperator.EQUAL
            )
            is True
        )
        assert (
            base.evaluate_score(
                0.8, ScoreType.NUMERIC, threshold=0.7, threshold_operator=ThresholdOperator.EQUAL
            )
            is False
        )
        assert (
            base.evaluate_score(
                0.8,
                ScoreType.NUMERIC,
                threshold=0.7,
                threshold_operator=ThresholdOperator.NOT_EQUAL,
            )
            is True
        )
        assert (
            base.evaluate_score(
                0.7,
                ScoreType.NUMERIC,
                threshold=0.7,
                threshold_operator=ThresholdOperator.NOT_EQUAL,
            )
            is False
        )

    def test_evaluate_score_binary(self):
        """Test score evaluation for binary score types."""
        base = MockRhesisMetricBase("test", reference_score="true")

        # Test binary evaluation (only = and != should work)
        assert (
            base.evaluate_score(
                "true",
                ScoreType.BINARY,
                reference_score="true",
                threshold_operator=ThresholdOperator.EQUAL,
            )
            is True
        )
        assert (
            base.evaluate_score(
                "false",
                ScoreType.BINARY,
                reference_score="true",
                threshold_operator=ThresholdOperator.EQUAL,
            )
            is False
        )
        assert (
            base.evaluate_score(
                "false",
                ScoreType.BINARY,
                reference_score="true",
                threshold_operator=ThresholdOperator.NOT_EQUAL,
            )
            is True
        )
        assert (
            base.evaluate_score(
                "true",
                ScoreType.BINARY,
                reference_score="true",
                threshold_operator=ThresholdOperator.NOT_EQUAL,
            )
            is False
        )

    def test_evaluate_score_categorical(self):
        """Test score evaluation for categorical score types."""
        base = MockRhesisMetricBase("test", reference_score="excellent")

        # Test categorical evaluation
        assert (
            base.evaluate_score(
                "excellent",
                ScoreType.CATEGORICAL,
                reference_score="excellent",
                threshold_operator=ThresholdOperator.EQUAL,
            )
            is True
        )
        assert (
            base.evaluate_score(
                "good",
                ScoreType.CATEGORICAL,
                reference_score="excellent",
                threshold_operator=ThresholdOperator.EQUAL,
            )
            is False
        )
        assert (
            base.evaluate_score(
                "good",
                ScoreType.CATEGORICAL,
                reference_score="excellent",
                threshold_operator=ThresholdOperator.NOT_EQUAL,
            )
            is True
        )
        assert (
            base.evaluate_score(
                "excellent",
                ScoreType.CATEGORICAL,
                reference_score="excellent",
                threshold_operator=ThresholdOperator.NOT_EQUAL,
            )
            is False
        )

    def test_evaluate_score_defaults(self):
        """Test that default operators are set correctly based on score type."""
        base_numeric = MockRhesisMetricBase("test", threshold=0.7)
        base_binary = MockRhesisMetricBase("test", reference_score="true")
        base_categorical = MockRhesisMetricBase("test", reference_score="excellent")

        # Default for numeric should be >=
        assert base_numeric.evaluate_score(0.8, ScoreType.NUMERIC) is True  # 0.8 >= 0.7
        assert base_numeric.evaluate_score(0.6, ScoreType.NUMERIC) is False  # 0.6 < 0.7

        # Default for binary should be =
        assert base_binary.evaluate_score("true", ScoreType.BINARY) is True
        assert base_binary.evaluate_score("false", ScoreType.BINARY) is False

        # Default for categorical should be =
        assert base_categorical.evaluate_score("excellent", ScoreType.CATEGORICAL) is True
        assert base_categorical.evaluate_score("good", ScoreType.CATEGORICAL) is False


def test_reference_score_requirements():
    """Test that reference_score is properly required for binary and categorical metrics."""

    # Test that categorical metrics require reference_score
    with pytest.raises(ValueError, match="reference_score is required for categorical score type"):
        RhesisPromptMetric(
            name="categorical_metric",
            evaluation_prompt="Rate quality",
            evaluation_steps="Steps",
            reasoning="Reasoning",
            score_type=ScoreType.CATEGORICAL,
            # Missing reference_score
        )

    # Test that binary metrics get a default reference_score if not provided
    binary_metric = RhesisPromptMetric(
        name="binary_metric",
        evaluation_prompt="Is correct?",
        evaluation_steps="Steps",
        reasoning="Reasoning",
        score_type=ScoreType.BINARY,
        # No reference_score provided, should default to "true"
    )
    assert binary_metric.reference_score == "true"

    # Test that numeric metrics don't use reference_score
    numeric_metric = RhesisPromptMetric(
        name="numeric_metric",
        evaluation_prompt="Rate quality",
        evaluation_steps="Steps",
        reasoning="Reasoning",
        score_type=ScoreType.NUMERIC,
        min_score=1.0,
        max_score=5.0,
        threshold=0.7,
    )
    assert numeric_metric.reference_score is None
    assert numeric_metric.threshold == 0.7


def test_evaluate_score_error_cases():
    """Test error cases in score evaluation."""
    base = MockRhesisMetricBase("test")

    # Test missing threshold for numeric
    with pytest.raises(ValueError, match="Threshold is required for numeric score type"):
        base.evaluate_score(0.8, ScoreType.NUMERIC)

    # Test missing reference_score for binary
    with pytest.raises(ValueError, match="Reference score is required for binary score type"):
        base.evaluate_score("true", ScoreType.BINARY)

    # Test missing reference_score for categorical
    with pytest.raises(ValueError, match="Reference score is required for categorical score type"):
        base.evaluate_score("excellent", ScoreType.CATEGORICAL)


if __name__ == "__main__":
    pytest.main([__file__])

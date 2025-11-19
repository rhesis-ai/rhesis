"""Tests for DeepEval conversational metrics."""

from unittest.mock import MagicMock

import pytest

from rhesis.sdk.metrics import ConversationHistory, DeepEvalTurnRelevancy
from rhesis.sdk.metrics.base import MetricType, ScoreType
from rhesis.sdk.models.base import BaseLLM


@pytest.fixture
def mock_model():
    """Create a mock LLM model for testing."""
    mock = MagicMock(spec=BaseLLM)
    mock.get_model_name.return_value = "mock-model"
    mock.generate.return_value = {"response": "test response"}
    return mock


@pytest.fixture
def sample_conversation():
    """Create a sample conversation for testing."""
    return ConversationHistory.from_messages(
        [
            {"role": "user", "content": "What insurance types do you offer?"},
            {"role": "assistant", "content": "We offer auto, home, and life insurance."},
            {"role": "user", "content": "Tell me more about auto insurance."},
            {
                "role": "assistant",
                "content": "Auto insurance includes liability and collision coverage.",
            },
        ]
    )


def test_turn_relevancy_initialization(mock_model):
    """Test Turn Relevancy metric initialization."""
    metric = DeepEvalTurnRelevancy(threshold=0.7, window_size=5, model=mock_model)

    assert metric.name == "turn_relevancy"
    assert metric.threshold == 0.7
    assert metric.window_size == 5
    assert metric.metric_type == MetricType.CONVERSATIONAL
    assert metric.score_type == ScoreType.NUMERIC


def test_turn_relevancy_default_initialization(mock_model):
    """Test Turn Relevancy metric with default values."""
    metric = DeepEvalTurnRelevancy(model=mock_model)

    assert metric.name == "turn_relevancy"
    assert metric.threshold == 0.5
    assert metric.window_size == 10


def test_turn_relevancy_model_update(mock_model):
    """Test updating model after initialization."""
    metric = DeepEvalTurnRelevancy(threshold=0.5, model=mock_model)

    # Create another mock model
    new_model = MagicMock(spec=BaseLLM)
    new_model.get_model_name.return_value = "new-mock-model"

    # Update model
    metric.model = new_model

    assert metric.model == new_model


def test_turn_relevancy_format_conversion(mock_model):
    """Test that standard format is converted correctly to DeepEval format."""
    conv = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "Test message"},
            {"role": "assistant", "content": "Test response", "tool_calls": [{"id": "1"}]},
        ]
    )

    metric = DeepEvalTurnRelevancy(model=mock_model)

    # Test the conversion method
    deepeval_test_case = metric._to_deepeval_format(conv)

    assert len(deepeval_test_case.turns) == 2
    assert deepeval_test_case.turns[0].role == "user"
    assert deepeval_test_case.turns[0].content == "Test message"
    assert deepeval_test_case.turns[1].role == "assistant"
    assert deepeval_test_case.turns[1].content == "Test response"

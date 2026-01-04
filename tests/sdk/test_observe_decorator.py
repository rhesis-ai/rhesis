"""Tests for @observe decorator."""

import pytest

from rhesis.sdk.decorators import observe


def test_observe_decorator_basic():
    """Test basic @observe decorator functionality."""

    @observe()
    def test_function(x: int) -> int:
        return x * 2

    # Function should execute normally
    result = test_function(5)
    assert result == 10


def test_observe_decorator_with_name():
    """Test @observe decorator with custom name."""

    @observe(name="custom_name")
    def test_function(x: int) -> int:
        return x * 2

    result = test_function(5)
    assert result == 10


def test_observe_decorator_with_span_name():
    """Test @observe decorator with custom span name."""

    @observe(span_name="ai.llm.invoke")
    def test_function(prompt: str) -> str:
        return f"Response to: {prompt}"

    result = test_function("test prompt")
    assert result == "Response to: test prompt"


def test_observe_decorator_with_attributes():
    """Test @observe decorator with custom attributes."""

    @observe(model="gpt-4", temperature=0.7)
    def test_function(prompt: str) -> str:
        return f"Response to: {prompt}"

    result = test_function("test prompt")
    assert result == "Response to: test prompt"


def test_observe_decorator_with_exception():
    """Test @observe decorator when function raises exception."""

    @observe()
    def test_function():
        raise ValueError("Test error")

    # Exception should be propagated
    with pytest.raises(ValueError, match="Test error"):
        test_function()

"""Tests for FunctionRegistry."""

import pytest

from rhesis.sdk.connector.registry import FunctionRegistry


@pytest.fixture
def registry():
    """Create a function registry for testing."""
    return FunctionRegistry()


@pytest.fixture
def sample_function():
    """Sample function for testing."""

    def sample_func(x: int, y: str = "default") -> str:
        """Sample function with type hints."""
        return f"{x}: {y}"

    return sample_func


def test_registry_initialization(registry):
    """Test registry initializes with empty storage."""
    assert registry.count() == 0
    assert registry.get_all_metadata() == []


def test_register_function(registry, sample_function):
    """Test registering a function."""
    metadata = {"description": "test function", "tags": ["test"]}

    registry.register("sample_func", sample_function, metadata)

    assert registry.count() == 1
    assert registry.has("sample_func")
    assert registry.get("sample_func") == sample_function


def test_register_multiple_functions(registry, sample_function):
    """Test registering multiple functions."""

    def another_func():
        return "another"

    registry.register("func1", sample_function, {})
    registry.register("func2", another_func, {})

    assert registry.count() == 2
    assert registry.has("func1")
    assert registry.has("func2")


def test_get_nonexistent_function(registry):
    """Test getting a function that doesn't exist."""
    result = registry.get("nonexistent")
    assert result is None


def test_has_function(registry, sample_function):
    """Test checking if function exists."""
    assert not registry.has("sample_func")

    registry.register("sample_func", sample_function, {})

    assert registry.has("sample_func")


def test_get_all_metadata(registry, sample_function):
    """Test getting all function metadata."""

    def another_func(a: str) -> int:
        return len(a)

    registry.register("func1", sample_function, {"desc": "first"})
    registry.register("func2", another_func, {"desc": "second"})

    metadata_list = registry.get_all_metadata()

    assert len(metadata_list) == 2
    assert all(hasattr(m, "name") for m in metadata_list)
    assert all(hasattr(m, "parameters") for m in metadata_list)
    assert all(hasattr(m, "return_type") for m in metadata_list)


def test_extract_function_signature(registry, sample_function):
    """Test extracting function signature."""
    registry.register("sample_func", sample_function, {})

    metadata_list = registry.get_all_metadata()
    metadata = metadata_list[0]

    assert "x" in metadata.parameters
    assert "y" in metadata.parameters
    assert metadata.parameters["x"]["type"] == "<class 'int'>"
    assert metadata.parameters["y"]["type"] == "<class 'str'>"
    assert metadata.parameters["y"]["default"] == "default"
    assert metadata.return_type == "<class 'str'>"


def test_function_without_annotations(registry):
    """Test function without type annotations."""

    def no_annotations(x, y):
        return x + y

    registry.register("no_annotations", no_annotations, {})

    metadata_list = registry.get_all_metadata()
    metadata = metadata_list[0]

    assert "x" in metadata.parameters
    assert "y" in metadata.parameters
    assert metadata.parameters["x"]["type"] == "Any"
    assert metadata.parameters["y"]["type"] == "Any"
    assert metadata.return_type == "Any"


def test_register_overwrites_existing(registry, sample_function):
    """Test that registering with same name overwrites."""

    def new_func():
        return "new"

    registry.register("func", sample_function, {"version": "1"})
    registry.register("func", new_func, {"version": "2"})

    assert registry.count() == 1
    assert registry.get("func") == new_func

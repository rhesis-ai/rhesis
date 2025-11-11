# Penelope Testing Guide

> **Unit testing patterns for the Penelope testing agent**

This guide covers testing patterns specific to Penelope, including mocking strategies, fixture usage, and test organization inspired by the SDK test suite.

## Table of Contents

- [Test Architecture](#test-architecture)
- [Directory Structure](#directory-structure)
- [Configuration & Setup](#configuration--setup)
- [Unit Testing Patterns](#unit-testing-patterns)
- [Mocking Strategies](#mocking-strategies)
- [Running Tests](#running-tests)

## Test Architecture

### Design Principles

1. **Module-based organization**: Tests mirror the source code structure
2. **Comprehensive mocking**: External dependencies are mocked to ensure unit isolation
3. **Shared fixtures**: Common test objects defined in `conftest.py`
4. **Clear test names**: Descriptive names that explain what is being tested
5. **SDK-inspired patterns**: Following the same patterns used in SDK tests

### Test Categories

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test complete workflows (in `tests/` root, not covered here)

## Directory Structure

```
tests/penelope/
├── README.md                    # This guide
├── conftest.py                  # Shared fixtures and utilities
├── __init__.py                  # Package marker
├── test_config.py              # Configuration module tests
├── test_context.py             # Context and state management tests
├── test_schemas.py             # Pydantic schema tests
├── test_utils.py               # Utility function tests
├── targets/                    # Target implementation tests
│   ├── __init__.py
│   ├── test_base.py           # Base Target class tests
│   └── test_endpoint.py       # EndpointTarget tests
├── tools/                      # Tool implementation tests
│   ├── __init__.py
│   ├── test_base.py           # Base Tool class tests
│   ├── test_analysis.py       # AnalyzeTool and ExtractTool tests
│   └── test_target_interaction.py  # TargetInteractionTool tests
└── prompts/                    # Prompt system tests
    ├── __init__.py
    ├── test_base.py           # PromptTemplate tests
    └── test_loader.py         # PromptLoader tests
```

## Configuration & Setup

### Shared Fixtures (conftest.py)

The `conftest.py` file provides shared fixtures used across tests:

```python
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_llm():
    """Mock LLM instance for testing"""
    mock = Mock(spec=BaseLLM)
    mock.generate.return_value = {"reasoning": "Test", "tool_name": "test_tool", "parameters": {}}
    return mock

@pytest.fixture
def mock_target():
    """Mock Target instance for testing"""
    # Returns a concrete implementation of Target
    ...

@pytest.fixture
def mock_tool():
    """Mock Tool instance for testing"""
    # Returns a concrete implementation of Tool
    ...
```

### Test Dependencies

Tests use:
- `pytest`: Test framework
- `unittest.mock`: Mocking library (Mock, patch)
- `pydantic`: For schema validation testing

## Unit Testing Patterns

### Pattern 1: Testing Abstract Base Classes

When testing abstract classes, verify they cannot be instantiated and that concrete implementations work:

```python
def test_target_cannot_be_instantiated():
    """Test that Target cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Target()

def test_target_abstract_methods():
    """Test that Target has expected abstract methods."""
    assert hasattr(Target, "send_message")
    assert Target.send_message.__isabstractmethod__
```

### Pattern 2: Testing Concrete Implementations

Test concrete methods on abstract classes by creating minimal implementations:

```python
def test_target_concrete_methods():
    """Test Target concrete method (get_tool_documentation)."""
    class TestTarget(Target):
        @property
        def target_type(self) -> str:
            return "test"
        
        # Implement all abstract methods...
        
    target = TestTarget()
    doc = target.get_tool_documentation()
    assert "Target Type: test" in doc
```

### Pattern 3: Testing with Mocks

Use mocks to isolate units under test:

```python
@patch("rhesis.penelope.targets.endpoint.Endpoint")
def test_endpoint_target_initialization_with_endpoint_id(mock_endpoint_class):
    """Test EndpointTarget initialization with endpoint_id."""
    mock_endpoint = Mock()
    mock_endpoint.id = "endpoint-123"
    mock_endpoint_class.from_id.return_value = mock_endpoint
    
    target = EndpointTarget(endpoint_id="endpoint-123")
    
    mock_endpoint_class.from_id.assert_called_once_with("endpoint-123")
    assert target.endpoint_id == "endpoint-123"
```

### Pattern 4: Testing Pydantic Schemas

Test schema validation and default values:

```python
def test_schema_creation():
    """Test schema initialization."""
    obj = MySchema(field1="value1", field2="value2")
    assert obj.field1 == "value1"
    assert obj.field2 == "value2"

def test_schema_validation():
    """Test schema validates required fields."""
    with pytest.raises(ValidationError):
        MySchema(field1="value1")  # Missing field2
```

### Pattern 5: Testing Configuration

Test configuration with environment variables using `monkeypatch`:

```python
def test_config_env_variable(monkeypatch):
    """Test that environment variable overrides default."""
    PenelopeConfig.reset()
    monkeypatch.setenv("PENELOPE_LOG_LEVEL", "ERROR")
    
    level = PenelopeConfig.get_log_level()
    assert level == "ERROR"
    
    # Cleanup
    PenelopeConfig.reset()
```

### Pattern 6: Testing Error Handling

Test both success and failure paths:

```python
def test_tool_execute_success(mock_target):
    """Test tool executes successfully."""
    tool = TargetInteractionTool(mock_target)
    result = tool.execute(message="Hello")
    
    assert result.success is True
    assert "response" in result.output

def test_tool_execute_error(mock_target):
    """Test tool handles errors correctly."""
    tool = TargetInteractionTool(mock_target)
    mock_target.send_message = Mock(side_effect=RuntimeError("Error"))
    
    result = tool.execute(message="Hello")
    
    assert result.success is False
    assert "Error" in result.error
```

## Mocking Strategies

### Mocking LLM Models

```python
@pytest.fixture
def mock_llm():
    mock = Mock(spec=BaseLLM)
    mock.generate.return_value = {
        "reasoning": "Test reasoning",
        "tool_name": "test_tool",
        "parameters": {},
    }
    mock.get_model_name.return_value = "MockLLM"
    return mock
```

### Mocking Targets

```python
@pytest.fixture
def mock_target():
    class MockTarget(Target):
        @property
        def target_type(self) -> str:
            return "mock"
        
        def send_message(self, message: str, session_id=None, **kwargs):
            return TargetResponse(
                success=True,
                content="Mock response",
                session_id=session_id or "session-123",
            )
        
        # Implement other abstract methods...
    
    return MockTarget()
```

### Mocking External Dependencies

```python
@patch("rhesis.penelope.targets.endpoint.Endpoint")
def test_with_mocked_dependency(mock_endpoint_class):
    # Configure mock
    mock_endpoint_class.from_id.return_value = some_mock_endpoint
    
    # Test code that uses Endpoint.from_id()
    ...
```

## Running Tests

### All Penelope Tests

```bash
# From project root
pytest tests/penelope/ -v

# From penelope directory  
cd penelope
pytest ../tests/penelope/ -v
```

### Specific Test Files

```bash
# Test configuration
pytest tests/penelope/test_config.py -v

# Test targets
pytest tests/penelope/targets/ -v

# Test tools
pytest tests/penelope/tools/ -v
```

### With Coverage

```bash
# Generate coverage report
pytest tests/penelope/ --cov=rhesis.penelope --cov-report=html

# View coverage
open htmlcov/index.html
```

### Running Specific Tests

```bash
# Single test function
pytest tests/penelope/test_config.py::test_config_default_log_level -v

# Test pattern matching
pytest tests/penelope/ -k "config" -v
```

## Best Practices

### Writing Tests

1. **One assertion per test concept**: Keep tests focused
2. **Descriptive names**: `test_what_when_expected` format
3. **Arrange-Act-Assert**: Clear test structure
4. **Test both success and failure**: Cover edge cases
5. **Use fixtures**: Reuse common setup via `conftest.py`

### Test Organization

1. **Mirror source structure**: Tests match module organization
2. **Group related tests**: Use classes when beneficial
3. **Document complex tests**: Add docstrings explaining intent
4. **Keep tests independent**: No interdependencies between tests

### Mocking Guidelines

1. **Mock external dependencies**: APIs, file system, network
2. **Don't mock what you're testing**: Test the actual code
3. **Use `spec=` parameter**: Ensures mocks match real interfaces
4. **Verify mock calls**: Use `assert_called_once_with()` etc.

## Additional Resources

- [Main Testing Guide](../README.md) - Universal testing principles
- [SDK Testing Guide](../sdk/README.md) - SDK testing patterns
- [pytest Documentation](https://docs.pytest.org/) - pytest framework
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html) - Mocking library

---

**Happy Testing!**

*This guide follows the same patterns as the SDK test suite for consistency across the project.*


"""Tests for bind parameter functionality in endpoint decorator."""

from unittest.mock import MagicMock

import pytest

from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.connector.registry import FunctionRegistry


@pytest.fixture
def mock_client(monkeypatch):
    """Create a mock RhesisClient for testing."""
    client = MagicMock(spec=RhesisClient)
    client._connector_manager = None
    client._tracer = MagicMock()
    client._tracer.trace_execution = lambda name, func, args, kwargs, span: func(*args, **kwargs)
    client._tracer.trace_execution_async = lambda name, func, args, kwargs, span: func(
        *args, **kwargs
    )

    # Mock the default client
    import rhesis.sdk.decorators as decorators

    monkeypatch.setattr(decorators, "_default_client", client)

    return client


@pytest.fixture
def registry():
    """Create a function registry for testing."""
    return FunctionRegistry()


def test_bind_static_value(mock_client):
    """Test binding a static value."""
    config = {"api_key": "test-key", "timeout": 30}

    @endpoint(bind={"config": config})
    def process_request(config, input: str) -> dict:
        return {"output": f"Using {config['api_key']}: {input}"}

    # Call the function
    result = process_request(input="test message")

    assert result["output"] == "Using test-key: test message"


def test_bind_callable(mock_client):
    """Test binding a callable that's evaluated at call time."""
    call_count = [0]

    def get_db():
        call_count[0] += 1
        return f"db_connection_{call_count[0]}"

    @endpoint(bind={"db": get_db})
    def query_data(db, input: str) -> dict:
        return {"output": f"{db}: {input}"}

    # Call multiple times
    result1 = query_data(input="query1")
    result2 = query_data(input="query2")

    # Callable should be evaluated each time
    assert result1["output"] == "db_connection_1: query1"
    assert result2["output"] == "db_connection_2: query2"
    assert call_count[0] == 2


def test_bind_multiple_params(mock_client):
    """Test binding multiple parameters."""
    config = {"env": "test"}

    def get_user():
        return {"id": "user123", "name": "Test User"}

    @endpoint(
        bind={
            "config": config,
            "user": get_user,
        }
    )
    def authenticated_query(config, user, input: str) -> dict:
        return {"output": f"User {user['name']} in {config['env']}: {input}"}

    result = authenticated_query(input="test query")

    assert result["output"] == "User Test User in test: test query"


def test_bind_does_not_override_provided_params(mock_client):
    """Test that bound params don't override explicitly provided params."""

    @endpoint(bind={"db": lambda: "default_db"})
    def query_data(db, input: str) -> dict:
        return {"output": f"{db}: {input}"}

    # Explicitly provide db parameter
    result = query_data(db="custom_db", input="query")

    # Should use the provided value, not the bound one
    assert result["output"] == "custom_db: query"


def test_bind_async_function(mock_client):
    """Test binding parameters in async functions."""
    config = {"timeout": 30}

    @endpoint(bind={"config": config})
    async def async_process(config, input: str) -> dict:
        return {"output": f"Timeout {config['timeout']}: {input}"}

    # Test async execution
    import asyncio

    result = asyncio.run(async_process(input="async test"))

    assert result["output"] == "Timeout 30: async test"


def test_bind_params_excluded_from_signature(registry):
    """Test that bound parameters are excluded from function signature."""

    def sample_func(db, config, input: str, session_id: str = None) -> dict:
        return {"output": "test"}

    # Register with bound params
    metadata = {"_bound_params": ["db", "config"]}
    registry.register("sample_func", sample_func, metadata)

    # Get metadata
    metadata_list = registry.get_all_metadata()
    func_metadata = metadata_list[0]

    # Only input and session_id should be in signature
    assert "input" in func_metadata.parameters
    assert "session_id" in func_metadata.parameters
    assert "db" not in func_metadata.parameters
    assert "config" not in func_metadata.parameters


def test_bind_params_stored_in_metadata(mock_client):
    """Test that bound parameter names are stored in metadata."""

    @endpoint(bind={"db": lambda: "db", "user": lambda: "user"})
    def query_data(db, user, input: str) -> dict:
        return {"output": "test"}

    # Check that register_endpoint was called with correct metadata
    mock_client.register_endpoint.assert_called_once()
    call_args = mock_client.register_endpoint.call_args
    metadata = call_args[0][2]  # Third argument is metadata

    assert "_bound_params" in metadata
    assert "db" in metadata["_bound_params"]
    assert "user" in metadata["_bound_params"]


def test_bind_with_lambda_expressions(mock_client):
    """Test binding with lambda expressions."""

    @endpoint(
        bind={
            "multiplier": lambda: 2,
            "prefix": lambda: "Result: ",
        }
    )
    def calculate(multiplier, prefix, input: int) -> dict:
        return {"output": f"{prefix}{input * multiplier}"}

    result = calculate(input=5)

    assert result["output"] == "Result: 10"


def test_bind_empty_dict(mock_client):
    """Test that empty bind dict works correctly."""

    @endpoint(bind={})
    def simple_func(input: str) -> dict:
        return {"output": input}

    result = simple_func(input="test")

    assert result["output"] == "test"


def test_bind_none(mock_client):
    """Test that bind=None works correctly."""

    @endpoint(bind=None)
    def simple_func(input: str) -> dict:
        return {"output": input}

    result = simple_func(input="test")

    assert result["output"] == "test"


def test_bind_with_observe_false(mock_client):
    """Test that bind works when observe=False."""
    config = {"key": "value"}

    @endpoint(bind={"config": config}, observe=False)
    def untraced_func(config, input: str) -> dict:
        return {"output": f"{config['key']}: {input}"}

    result = untraced_func(input="test")

    assert result["output"] == "value: test"


def test_bind_with_request_mapping(mock_client):
    """Test that bind works together with request_mapping."""
    config = {"env": "test"}

    @endpoint(
        bind={"config": config},
        request_mapping={
            "user_query": "{{ input }}",
        },
    )
    def mapped_func(config, user_query: str) -> dict:
        return {"output": f"{config['env']}: {user_query}"}

    result = mapped_func(user_query="test query")

    assert result["output"] == "test: test query"


def test_bind_callable_exception_handling(mock_client):
    """Test that exceptions in bound callables are propagated."""

    def failing_dependency():
        raise ValueError("Dependency initialization failed")

    @endpoint(bind={"db": failing_dependency})
    def query_data(db, input: str) -> dict:
        return {"output": "test"}

    # Should raise the exception from the callable
    with pytest.raises(ValueError, match="Dependency initialization failed"):
        query_data(input="test")


def test_registry_signature_extraction_with_exclusions(registry):
    """Test signature extraction with parameter exclusions."""

    def complex_func(
        db, config, user, input: str, session_id: str = None, context: list = None
    ) -> dict:
        return {"output": "test"}

    # Register with some params excluded
    metadata = {"_bound_params": ["db", "config", "user"]}
    registry.register("complex_func", complex_func, metadata)

    # Get signature
    metadata_list = registry.get_all_metadata()
    func_metadata = metadata_list[0]

    # Check that only non-bound params are in signature
    assert len(func_metadata.parameters) == 3
    assert "input" in func_metadata.parameters
    assert "session_id" in func_metadata.parameters
    assert "context" in func_metadata.parameters

    # Check that bound params are excluded
    assert "db" not in func_metadata.parameters
    assert "config" not in func_metadata.parameters
    assert "user" not in func_metadata.parameters


def test_bind_with_generator_dependency(mock_client):
    """Test binding with generator-based dependencies."""

    def get_db_generator():
        """Simulate FastAPI-style Depends with generator."""
        db = "db_connection"
        yield db
        # Cleanup would happen here

    @endpoint(bind={"db": lambda: next(get_db_generator())})
    def query_with_generator(db, input: str) -> dict:
        return {"output": f"{db}: {input}"}

    result = query_with_generator(input="test")

    assert result["output"] == "db_connection: test"

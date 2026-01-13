"""Tests for @endpoint decorator bind parameter functionality."""

from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.decorators import endpoint


@pytest.fixture
def mock_client():
    """Create a mock RhesisClient for testing."""
    with patch("rhesis.sdk.decorators._state._default_client") as mock:
        mock._connector_manager = None
        mock._tracer = Mock()

        # The wrapper already calls inject_bound_params and modifies kwargs
        # So we just need to call the function with the provided args and kwargs
        def sync_side_effect(name, func, args, kwargs, span):
            # At this point, kwargs already has bound parameters injected
            return func(*args, **kwargs)

        mock._tracer.trace_execution = Mock(side_effect=sync_side_effect)

        # Async side effect needs to properly await the coroutine
        async def async_side_effect(name, func, args, kwargs, span):
            # At this point, kwargs already has bound parameters injected
            return await func(*args, **kwargs)

        mock._tracer.trace_execution_async = Mock(side_effect=async_side_effect)
        mock.register_endpoint = Mock()
        yield mock


class TestBindParameterInjection:
    """Tests for bind parameter injection functionality."""

    def test_bind_static_value(self, mock_client):
        """Test binding a static value when parameter is not provided."""
        # Use a non-callable object to ensure it's not treated as a callable bind
        db_mock = {"type": "database", "connection": "test"}

        @endpoint(bind={"db": db_mock})
        def query_data(db, input: str) -> str:
            assert db == db_mock  # Verify the correct db was injected
            return f"Querying {input}"

        result = query_data(input="test")

        assert result == "Querying test"

    def test_bind_callable(self, mock_client):
        """Test binding a callable that gets evaluated at call time."""
        call_count = {"count": 0}

        def get_db():
            call_count["count"] += 1
            return f"db_session_{call_count['count']}"

        @endpoint(bind={"db": get_db})
        def query_data(db, input: str) -> str:
            return f"{input}:{db}"

        result1 = query_data(input="test1")
        result2 = query_data(input="test2")

        assert result1 == "test1:db_session_1"
        assert result2 == "test2:db_session_2"
        assert call_count["count"] == 2  # Callable called twice

    def test_bind_skips_when_provided_as_kwarg(self, mock_client):
        """Test that bind is skipped when parameter is provided as keyword argument."""
        bound_db = Mock(name="bound_db")
        provided_db = Mock(name="provided_db")

        @endpoint(bind={"db": bound_db})
        def query_data(db, input: str) -> str:
            assert db is provided_db  # Verify provided_db was used, not bound_db
            return f"Querying {input}"

        result = query_data(input="test", db=provided_db)

        assert result == "Querying test"

    def test_bind_skips_when_provided_as_positional_arg(self, mock_client):
        """Test that bind is skipped when parameter is provided as positional argument."""
        bound_db = Mock(name="bound_db")
        provided_db = Mock(name="provided_db")

        @endpoint(bind={"db": bound_db})
        def query_data(db, input: str) -> str:
            assert db is provided_db  # Verify provided_db was used, not bound_db
            return f"Querying {input}"

        result = query_data(db=provided_db, input="test")

        assert result == "Querying test"

    def test_bind_mixed_provided_and_not_provided(self, mock_client):
        """Test bind with mix of provided and not provided parameters."""
        bound_db = "bound_db_value"
        bound_user = "bound_user_value"
        provided_user = "provided_user_value"

        @endpoint(bind={"db": bound_db, "user": bound_user})
        def query_data(db, user, input: str) -> str:
            assert db == bound_db  # db should be bound
            assert user == provided_user  # user should be provided
            return f"Querying {input}"

        result = query_data(user=provided_user, input="test")

        assert result == "Querying test"

    def test_bind_multiple_static_values(self, mock_client):
        """Test binding multiple static values."""
        db_mock = "db_value"
        config_mock = {"setting": "value"}

        @endpoint(bind={"db": db_mock, "config": config_mock})
        def process_data(db, config, input: str) -> str:
            assert db == db_mock
            assert config == config_mock
            return f"Processing {input}"

        result = process_data(input="test")

        assert result == "Processing test"

    def test_bind_multiple_callables(self, mock_client):
        """Test binding multiple callables."""
        db_count = {"count": 0}
        user_count = {"count": 0}

        def get_db():
            db_count["count"] += 1
            return f"db_{db_count['count']}"

        def get_user():
            user_count["count"] += 1
            return f"user_{user_count['count']}"

        @endpoint(bind={"db": get_db, "user": get_user})
        def query_data(db, user, input: str) -> str:
            return f"{input}:{db}:{user}"

        result = query_data(input="test")

        assert result == "test:db_1:user_1"
        assert db_count["count"] == 1
        assert user_count["count"] == 1

    def test_bind_with_all_parameters_provided(self, mock_client):
        """Test bind when all parameters are already provided."""
        bound_db = Mock(name="bound_db")
        provided_db = Mock(name="provided_db")

        @endpoint(bind={"db": bound_db})
        def query_data(db, input: str) -> str:
            assert db is provided_db  # Bound value should not be used
            return f"Querying {input}"

        result = query_data(db=provided_db, input="test")

        assert result == "Querying test"

    def test_bind_with_no_parameters_provided(self, mock_client):
        """Test bind when no parameters are provided (all come from bind)."""
        db_mock = "db_value"
        user_mock = "user_value"

        @endpoint(bind={"db": db_mock, "user": user_mock})
        def query_data(db, user, input: str) -> str:
            assert db == db_mock
            assert user == user_mock
            return f"Querying {input}"

        result = query_data(input="test")

        assert result == "Querying test"

    def test_bind_with_default_parameters(self, mock_client):
        """Test bind with function that has default parameters."""
        db_mock = "db_value"

        @endpoint(bind={"db": db_mock})
        def query_data(db, input: str, limit: int = 10) -> str:
            assert db == db_mock
            return f"Querying {input}, limit={limit}"

        result = query_data(input="test")

        assert result == "Querying test, limit=10"

    def test_bind_with_lambda_callable(self, mock_client):
        """Test bind with lambda as callable."""
        call_count = {"count": 0}

        @endpoint(
    bind={
        "counter": lambda: (call_count.update(count=call_count["count"] + 1) or call_count["count"])
    }
)
        def increment(counter, value: int) -> int:
            return value + counter

        result1 = increment(value=5)
        result2 = increment(value=5)

        assert result1 == 6  # 5 + 1
        assert result2 == 7  # 5 + 2
        assert call_count["count"] == 2


class TestBindParameterAsync:
    """Tests for bind parameter injection with async functions."""

    @pytest.mark.asyncio
    async def test_bind_static_value_async(self, mock_client):
        """Test binding a static value in async function."""
        db_mock = {"type": "database"}

        @endpoint(bind={"db": db_mock})
        async def query_data_async(db, input: str) -> str:
            assert db == db_mock
            return f"Querying {input}"

        result = await query_data_async(input="test")

        assert result == "Querying test"

    @pytest.mark.asyncio
    async def test_bind_callable_async(self, mock_client):
        """Test binding a callable in async function."""
        call_count = {"count": 0}

        def get_db():
            call_count["count"] += 1
            return f"db_session_{call_count['count']}"

        @endpoint(bind={"db": get_db})
        async def query_data_async(db, input: str) -> str:
            return f"{input}:{db}"

        result = await query_data_async(input="test")

        assert result == "test:db_session_1"
        assert call_count["count"] == 1

    @pytest.mark.asyncio
    async def test_bind_skips_when_provided_as_kwarg_async(self, mock_client):
        """Test that bind is skipped when parameter provided as kwarg in async function."""
        bound_db = Mock(name="bound_db")
        provided_db = Mock(name="provided_db")

        @endpoint(bind={"db": bound_db})
        async def query_data_async(db, input: str) -> str:
            assert db is provided_db
            return f"Querying {input}"

        result = await query_data_async(input="test", db=provided_db)

        assert result == "Querying test"

    @pytest.mark.asyncio
    async def test_bind_skips_when_provided_as_positional_arg_async(self, mock_client):
        """Test that bind is skipped when parameter provided as positional arg in async function."""
        bound_db = Mock(name="bound_db")
        provided_db = Mock(name="provided_db")

        @endpoint(bind={"db": bound_db})
        async def query_data_async(db, input: str) -> str:
            assert db is provided_db
            return f"Querying {input}"

        result = await query_data_async(db=provided_db, input="test")

        assert result == "Querying test"

    @pytest.mark.asyncio
    async def test_bind_mixed_provided_and_not_provided_async(self, mock_client):
        """Test bind with mix of provided and not provided in async function."""
        bound_db = "bound_db_value"
        bound_user = "bound_user_value"
        provided_user = "provided_user_value"

        @endpoint(bind={"db": bound_db, "user": bound_user})
        async def query_data_async(db, user, input: str) -> str:
            assert db == bound_db
            assert user == provided_user
            return f"Querying {input}"

        result = await query_data_async(user=provided_user, input="test")

        assert result == "Querying test"


class TestBindParameterEdgeCases:
    """Tests for edge cases in bind parameter functionality."""

    def test_bind_with_complex_function_signature(self, mock_client):
        """Test bind with complex function signature (positional, keyword, defaults)."""
        db_mock = "db_value"
        user_mock = "user_value"

        @endpoint(bind={"db": db_mock, "user": user_mock})
        def complex_function(
            db, user, first_arg: str, second_arg: int = 5, third_arg: str = "default"
        ) -> str:
            assert db == db_mock
            assert user == user_mock
            return f"{first_arg}_{second_arg}_{third_arg}"

        result = complex_function(first_arg="test")

        assert result == "test_5_default"

    def test_bind_with_positional_only_parameters(self, mock_client):
        """Test bind respects positional-only parameters."""
        db_mock = "db_value"

        @endpoint(bind={"db": db_mock})
        def func_with_pos_only(input: str, /, db, keyword_arg: str) -> str:
            assert db == db_mock
            return f"{input}_{keyword_arg}"

        result = func_with_pos_only("pos", keyword_arg="kw")

        assert result == "pos_kw"

    def test_bind_with_keyword_only_parameters(self, mock_client):
        """Test bind respects keyword-only parameters."""
        db_mock = "db_value"

        @endpoint(bind={"db": db_mock})
        def func_with_kw_only(input: str, *, db, keyword_arg: str) -> str:
            assert db == db_mock
            return f"{input}_{keyword_arg}"

        result = func_with_kw_only("test", keyword_arg="kw")

        assert result == "test_kw"

    def test_bind_parameter_name_not_in_signature(self, mock_client):
        """Test bind with parameter name that doesn't exist in function signature."""
        # Bind parameters not in signature should be injected anyway (for **kwargs scenarios)
        db_mock = Mock(name="db")

        @endpoint(bind={"db": db_mock})
        def query_data(db, input: str) -> str:
            return f"Querying {input} with {db}"

        # Should work fine
        result = query_data(input="test")
        assert "Querying test" in result

    def test_bind_empty_dict(self, mock_client):
        """Test bind with empty dict (no bindings)."""
        @endpoint(bind={})
        def query_data(input: str) -> str:
            return f"Querying {input}"

        result = query_data("test")
        assert result == "Querying test"

    def test_bind_none(self, mock_client):
        """Test bind with None (no bindings)."""
        @endpoint(bind=None)
        def query_data(input: str) -> str:
            return f"Querying {input}"

        result = query_data("test")
        assert result == "Querying test"

    def test_bind_callable_returns_none(self, mock_client):
        """Test bind with callable that returns None."""
        @endpoint(bind={"db": lambda: None})
        def query_data(db, input: str) -> str:
            assert db is None
            return f"Querying {input}"

        result = query_data(input="test")
        assert result == "Querying test"

    def test_bind_with_observe_false(self, mock_client):
        """Test bind works with observe=False."""
        db_mock = "db_value"

        @endpoint(bind={"db": db_mock}, observe=False)
        def query_data(db, input: str) -> str:
            assert db == db_mock
            return f"Querying {input}"

        result = query_data(input="test")
        assert result == "Querying test"
        # Should register but not trace
        mock_client.register_endpoint.assert_called_once()
        mock_client._tracer.trace_execution.assert_not_called()


class TestBindParameterRealWorldScenario:
    """Tests simulating real-world scenarios with bind parameters."""

    def test_fastapi_style_dependency_injection(self, mock_client):
        """Test bind with FastAPI-style dependency injection pattern."""
        # Simulate FastAPI calling with all parameters as kwargs or positional args
        fastapi_db = Mock(name="fastapi_db")
        fastapi_user = Mock(name="fastapi_user")

        # Bind provides defaults for SDK remote invocation
        bound_db = Mock(name="bound_db")
        bound_user = Mock(name="bound_user")
        bound_org_id = "org-123"
        bound_user_id = "user-456"

        @endpoint(
            bind={
                "db": bound_db,
                "user": bound_user,
                "organization_id": bound_org_id,
                "user_id": bound_user_id,
            }
        )
        def search_mcp(
            query: str,
            tool_id: str,
            db,
            user,
            organization_id: str,
            user_id: str = None,
        ) -> str:
            # Verify FastAPI-provided values are used, not bound values
            assert db is fastapi_db
            assert user is fastapi_user
            assert organization_id == "org-789"
            assert user_id == "user-999"
            return "OK"

        # FastAPI call with all parameters provided (simulating real usage)
        result = search_mcp(
            query="test query",
            tool_id="tool-123",
            db=fastapi_db,
            user=fastapi_user,
            organization_id="org-789",
            user_id="user-999"
        )

        assert result == "OK"

    def test_sdk_remote_invocation_scenario(self, mock_client):
        """Test bind with SDK remote invocation (no parameters provided)."""
        # Simulate SDK remote invocation where only input is provided
        bound_db = "bound_db_value"
        bound_user = "bound_user_value"
        bound_org_id = "org-123"
        bound_user_id = "user-456"
        bound_tool_id = "tool-789"

        @endpoint(
            bind={
                "db": bound_db,
                "user": bound_user,
                "organization_id": bound_org_id,
                "user_id": bound_user_id,
                "tool_id": bound_tool_id,
            }
        )
        def search_mcp(
            query: str,
            tool_id: str,
            db,
            user,
            organization_id: str,
            user_id: str = None,
        ) -> str:
            # Verify all bound values are used
            assert db == bound_db
            assert user == bound_user
            assert organization_id == "org-123"
            assert user_id == "user-456"
            assert tool_id == "tool-789"
            return "OK"

        # SDK remote invocation (only query provided via request_mapping)
        result = search_mcp(query="test query")

        assert result == "OK"

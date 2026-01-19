"""Tests for generator-based dependency cleanup in @endpoint decorator.

This tests the new functionality that automatically cleans up generator-based
dependencies (similar to FastAPI's Depends with yield pattern).
"""

from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.decorators import endpoint


@pytest.fixture(autouse=True)
def setup_mock_client():
    """Set up a mock RhesisClient that's always available for tests."""
    with patch("rhesis.sdk.decorators._state._default_client") as mock_client:
        # Configure the mock client
        mock_client._connector_manager = None
        mock_client._tracer = Mock()
        mock_client.is_disabled = False  # Ensure client is not disabled

        # Mock tracer methods to execute functions directly
        def sync_execute(name, func, args, kwargs, span):
            return func(*args, **kwargs)

        async def async_execute(name, func, args, kwargs, span):
            return await func(*args, **kwargs)

        mock_client._tracer.trace_execution = Mock(side_effect=sync_execute)
        mock_client._tracer.trace_execution_async = Mock(side_effect=async_execute)
        mock_client.register_endpoint = Mock()

        yield mock_client


class TestGeneratorDependencyCleanup:
    """Tests for automatic cleanup of generator-based dependencies."""

    def test_generator_dependency_yields_value(self):
        """Test that generator-based dependency provides the yielded value."""
        def db_dependency():
            db_session = Mock(name="db_session")
            yield db_session

        @endpoint(bind={"db": db_dependency})
        def query_function(db, query: str) -> str:
            # Verify we get the actual db_session object, not the generator
            assert hasattr(db, "_mock_name")
            assert db._mock_name == "db_session"
            return f"Query: {query}"

        result = query_function(query="SELECT *")
        assert result == "Query: SELECT *"

    def test_generator_cleanup_is_called(self):
        """Test that generator finally block is executed after function completes."""
        cleanup_tracker = []

        def db_dependency():
            cleanup_tracker.append("setup")
            try:
                yield "db_connection"
            finally:
                cleanup_tracker.append("cleanup")

        @endpoint(bind={"db": db_dependency})
        def query_function(db, query: str) -> str:
            cleanup_tracker.append("execute")
            return f"{db}: {query}"

        result = query_function(query="test")

        assert result == "db_connection: test"
        assert cleanup_tracker == ["setup", "execute", "cleanup"]

    def test_generator_cleanup_on_exception(self):
        """Test that generator cleanup happens even when function raises exception."""
        cleanup_tracker = []

        def db_dependency():
            cleanup_tracker.append("setup")
            try:
                yield "db_connection"
            finally:
                cleanup_tracker.append("cleanup")

        @endpoint(bind={"db": db_dependency})
        def failing_function(db, query: str) -> str:
            cleanup_tracker.append("execute")
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function(query="test")

        # Cleanup should still happen
        assert cleanup_tracker == ["setup", "execute", "cleanup"]

    def test_multiple_generators_all_cleaned_up(self):
        """Test that multiple generator dependencies are all cleaned up."""
        cleanup_order = []

        def db_dependency():
            cleanup_order.append("db_setup")
            try:
                yield "db_connection"
            finally:
                cleanup_order.append("db_cleanup")

        def cache_dependency():
            cleanup_order.append("cache_setup")
            try:
                yield "cache_connection"
            finally:
                cleanup_order.append("cache_cleanup")

        @endpoint(bind={"db": db_dependency, "cache": cache_dependency})
        def query_with_cache(db, cache, query: str) -> str:
            cleanup_order.append("execute")
            return f"{db}+{cache}: {query}"

        result = query_with_cache(query="test")

        assert "db_connection" in result
        assert "cache_connection" in result
        # Both generators should be set up, function executed, then both cleaned up
        assert "db_setup" in cleanup_order
        assert "cache_setup" in cleanup_order
        assert "execute" in cleanup_order
        assert "db_cleanup" in cleanup_order
        assert "cache_cleanup" in cleanup_order

    def test_non_generator_callable_still_works(self):
        """Test that regular callables (non-generators) continue to work as before."""
        call_count = [0]

        def regular_dependency():
            call_count[0] += 1
            return f"connection_{call_count[0]}"

        @endpoint(bind={"db": regular_dependency})
        def query_function(db, query: str) -> str:
            return f"{db}: {query}"

        result1 = query_function(query="test1")
        result2 = query_function(query="test2")

        assert result1 == "connection_1: test1"
        assert result2 == "connection_2: test2"

    def test_static_value_still_works(self):
        """Test that static (non-callable) bind values continue to work."""
        static_config = {"host": "localhost", "port": 5432}

        @endpoint(bind={"config": static_config})
        def connect_function(config, dbname: str) -> str:
            return f"{config['host']}:{config['port']}/{dbname}"

        result = connect_function(dbname="testdb")
        assert result == "localhost:5432/testdb"

    def test_generator_with_context_manager_pattern(self):
        """Test generator simulating a context manager (like get_db())."""
        lifecycle = []

        def get_db_session():
            """Simulates FastAPI's Depends with context manager."""
            lifecycle.append("acquire_connection")
            lifecycle.append("begin_transaction")
            db = Mock(name="db_session")
            db.close = Mock()

            try:
                yield db
            finally:
                lifecycle.append("commit_transaction")
                db.close()
                lifecycle.append("close_connection")

        @endpoint(bind={"db": get_db_session})
        def save_data(db, data: str) -> str:
            lifecycle.append("execute_query")
            return f"Saved: {data}"

        result = save_data(data="test_data")

        assert result == "Saved: test_data"
        assert lifecycle == [
            "acquire_connection",
            "begin_transaction",
            "execute_query",
            "commit_transaction",
            "close_connection",
        ]

    def test_generator_not_called_when_param_provided(self):
        """Test that generator is not called if parameter is explicitly provided."""
        generator_called = [False]

        def db_dependency():
            generator_called[0] = True
            yield "bound_db"

        @endpoint(bind={"db": db_dependency})
        def query_function(db, query: str) -> str:
            return f"{db}: {query}"

        # Provide db explicitly - generator should not be called
        result = query_function(db="custom_db", query="test")

        assert result == "custom_db: test"
        assert not generator_called[0]

    @pytest.mark.asyncio
    async def test_generator_cleanup_with_async_function(self):
        """Test that generator cleanup works with async functions."""
        cleanup_tracker = []

        def db_dependency():
            cleanup_tracker.append("setup")
            try:
                yield "async_db"
            finally:
                cleanup_tracker.append("cleanup")

        @endpoint(bind={"db": db_dependency})
        async def async_query(db, query: str) -> str:
            cleanup_tracker.append("execute")
            return f"{db}: {query}"

        result = await async_query(query="test")

        assert result == "async_db: test"
        assert cleanup_tracker == ["setup", "execute", "cleanup"]

    @pytest.mark.asyncio
    async def test_async_generator_cleanup_on_exception(self):
        """Test generator cleanup in async function when exception occurs."""
        cleanup_tracker = []

        def db_dependency():
            cleanup_tracker.append("setup")
            try:
                yield "async_db"
            finally:
                cleanup_tracker.append("cleanup")

        @endpoint(bind={"db": db_dependency})
        async def failing_async(db, query: str) -> str:
            cleanup_tracker.append("execute")
            raise RuntimeError("Async error")

        with pytest.raises(RuntimeError, match="Async error"):
            await failing_async(query="test")

        assert cleanup_tracker == ["setup", "execute", "cleanup"]

    def test_observe_false_with_generator(self):
        """Test that generator cleanup works when observe=False."""
        cleanup_tracker = []

        def db_dependency():
            cleanup_tracker.append("setup")
            try:
                yield "db_connection"
            finally:
                cleanup_tracker.append("cleanup")

        @endpoint(bind={"db": db_dependency}, observe=False)
        def untraced_query(db, query: str) -> str:
            cleanup_tracker.append("execute")
            return f"{db}: {query}"

        result = untraced_query(query="test")

        assert result == "db_connection: test"
        assert cleanup_tracker == ["setup", "execute", "cleanup"]

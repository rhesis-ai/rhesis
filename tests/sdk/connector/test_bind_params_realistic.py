"""Realistic unit tests for bind parameter with infrastructure patterns.

These tests demonstrate real-world usage patterns simulating infrastructure
dependencies like database sessions, connection pools, and async operations.

Note: These are unit tests with realistic mocks, not integration tests.
For true integration tests with docker-compose backend, see tests/sdk/integration/.
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from rhesis.sdk import RhesisClient, endpoint

# ============================================================================
# Realistic Infrastructure Fixtures
# ============================================================================


@dataclass
class MockDBSession:
    """Mock database session that simulates SQLAlchemy behavior."""

    connection_id: str
    pool: "MockConnectionPool" = None
    is_closed: bool = False
    transaction_active: bool = False

    def query(self, model):
        """Simulate query operation."""
        if self.is_closed:
            raise RuntimeError("Cannot query on closed session")
        return self

    def filter(self, *args):
        """Simulate filter operation."""
        return self

    def all(self):
        """Simulate fetching all results."""
        return [
            {"id": 1, "name": f"User from {self.connection_id}"},
            {"id": 2, "name": f"Another user from {self.connection_id}"},
        ]

    def first(self):
        """Simulate fetching first result."""
        return {"id": 1, "name": f"User from {self.connection_id}"}

    def commit(self):
        """Simulate commit."""
        if self.is_closed:
            raise RuntimeError("Cannot commit on closed session")
        self.transaction_active = False

    def rollback(self):
        """Simulate rollback."""
        if self.is_closed:
            raise RuntimeError("Cannot rollback on closed session")
        self.transaction_active = False

    def close(self):
        """Close the session and release back to pool."""
        if not self.is_closed:
            self.is_closed = True
            if self.pool:
                self.pool.release_connection(self)

    def __enter__(self):
        """Context manager entry."""
        self.transaction_active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with transaction handling."""
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


@dataclass
class MockConnectionPool:
    """Simulates a database connection pool."""

    max_connections: int = 10
    active_connections: int = 0
    connection_counter: int = 0

    def get_connection(self) -> MockDBSession:
        """Get a connection from the pool."""
        if self.active_connections >= self.max_connections:
            raise RuntimeError("Connection pool exhausted")

        self.active_connections += 1
        self.connection_counter += 1
        return MockDBSession(connection_id=f"conn_{self.connection_counter}", pool=self)

    def release_connection(self, session: MockDBSession):
        """Release a connection back to the pool."""
        if self.active_connections > 0:
            self.active_connections -= 1


@dataclass
class AppConfig:
    """Realistic application configuration."""

    database_url: str = "postgresql://localhost/test"
    api_timeout: int = 30
    max_retries: int = 3
    debug: bool = False
    tenant_id: str = "org_test"


@dataclass
class AuthContext:
    """Realistic authentication context."""

    user_id: str
    username: str
    roles: list[str]
    organization_id: str
    is_authenticated: bool = True
    session_id: str = "session_123"

    def has_permission(self, permission: str) -> bool:
        """Check if user has permission."""
        return "admin" in self.roles or permission in self.roles


# Connection pool singleton
_connection_pool = MockConnectionPool()


def get_db_session() -> MockDBSession:
    """
    Get a database session from the pool (realistic pattern).

    Returns:
        Database session

    This simulates the pattern used in FastAPI with Depends(get_db)
    or SQLAlchemy session management. In real usage, you'd use a
    context manager, but for bind we return the session directly.
    """
    return _connection_pool.get_connection()


def get_config() -> AppConfig:
    """Get application configuration (realistic pattern)."""
    return AppConfig(tenant_id="org_test")


def get_current_user() -> AuthContext:
    """Get current authenticated user (realistic pattern)."""
    return AuthContext(
        user_id="user_123",
        username="test_user",
        roles=["user", "query_data"],
        organization_id="org_test",
    )


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_client(monkeypatch):
    """Create a mock RhesisClient for testing."""
    client = MagicMock(spec=RhesisClient)
    client._connector_manager = None
    client.is_disabled = False  # Ensure client is not disabled
    client._tracer = MagicMock()
    client._tracer.trace_execution = lambda name, func, args, kwargs, span: func(*args, **kwargs)
    client._tracer.trace_execution_async = lambda name, func, args, kwargs, span: func(
        *args, **kwargs
    )

    # Mock the default client
    import rhesis.sdk.decorators._state as decorators_state

    monkeypatch.setattr(decorators_state, "_default_client", client)

    return client


@pytest.fixture(autouse=True)
def reset_connection_pool():
    """Reset the connection pool between tests."""
    global _connection_pool
    _connection_pool = MockConnectionPool()
    yield
    # Ensure all connections are closed
    _connection_pool.active_connections = 0


# ============================================================================
# Integration Tests
# ============================================================================


def test_bind_with_database_session_lifecycle(mock_client):
    """Test that database sessions are properly created and closed."""

    @endpoint(bind={"db": get_db_session})
    def query_users(db, input: str) -> dict:
        """Query users with proper session management."""
        users = db.query("User").filter(f"name LIKE '{input}'").all()
        # Close session after use (in real code, use context manager)
        db.close()
        return {"output": users}

    # Execute multiple times
    result1 = query_users(input="test")
    result2 = query_users(input="another")

    # Each call should get a fresh session
    assert len(result1["output"]) == 2
    assert len(result2["output"]) == 2
    assert result1["output"][0]["name"] != result2["output"][0]["name"]

    # All sessions should be closed (active connections back to 0)
    assert _connection_pool.active_connections == 0


def test_bind_with_connection_pool_management(mock_client):
    """Test connection pool management with bind parameter."""

    @endpoint(bind={"db": get_db_session})
    def heavy_query(db, input: str) -> dict:
        """Simulate a heavy query."""
        result = db.query("LargeTable").filter(f"field = '{input}'").first()
        db.close()
        return {"output": result}

    # Execute multiple concurrent-like operations
    results = []
    for i in range(5):
        result = heavy_query(input=f"query_{i}")
        results.append(result)

    # All queries should complete successfully
    assert len(results) == 5
    assert all("output" in r for r in results)

    # Connection pool should be empty after all operations
    assert _connection_pool.active_connections == 0
    assert _connection_pool.connection_counter == 5  # 5 connections were created


def test_bind_with_transaction_rollback_on_error(mock_client):
    """Test that database transactions rollback on errors."""

    @endpoint(bind={"db": get_db_session})
    def failing_query(db, input: str) -> dict:
        """Query that simulates a failure."""
        db.transaction_active = True
        try:
            if input == "fail":
                raise ValueError("Simulated database error")
            db.commit()
            return {"output": "success"}
        finally:
            db.close()

    # Successful execution
    result = failing_query(input="success")
    assert result["output"] == "success"

    # Failed execution should raise but not leave connections open
    with pytest.raises(ValueError, match="Simulated database error"):
        failing_query(input="fail")

    # Connection should still be released
    assert _connection_pool.active_connections == 0


@pytest.mark.asyncio
async def test_bind_with_async_database_operations(mock_client):
    """Test bind with async database operations."""

    @endpoint(bind={"db": get_db_session})
    async def async_query(db, input: str) -> dict:
        """Async query with bind parameter."""
        try:
            await asyncio.sleep(0.01)  # Simulate async query
            users = db.query("User").filter(f"name = '{input}'").all()
            return {"output": users}
        finally:
            db.close()

    # Execute async query
    result = await async_query(input="test_user")

    assert len(result["output"]) == 2
    assert _connection_pool.active_connections == 0


def test_bind_with_multi_tenant_database_context(mock_client):
    """Test bind with tenant-specific database sessions."""

    def get_tenant_db(tenant_id: str):
        """Get database session with tenant context."""
        session = get_db_session()
        session.tenant_id = tenant_id  # Add tenant context
        return session

    @endpoint(
        bind={
            "db": lambda: get_tenant_db("org_test"),
            "user": get_current_user,
        }
    )
    def tenant_query(db, user, input: str) -> dict:
        """Query with tenant isolation."""
        try:
            # Verify tenant matches user's organization
            if hasattr(db, "tenant_id") and db.tenant_id != user.organization_id:
                return {"output": "Unauthorized", "error": "Tenant mismatch"}

            results = db.query("TenantData").filter(f"query = '{input}'").all()
            return {"output": results, "tenant": user.organization_id}
        finally:
            db.close()

    result = tenant_query(input="test")

    assert result["tenant"] == "org_test"
    assert len(result["output"]) == 2
    assert _connection_pool.active_connections == 0


def test_bind_with_configuration_and_auth(mock_client):
    """Test realistic pattern with config and auth context."""

    @endpoint(
        bind={
            "db": get_db_session,
            "config": get_config,
            "user": get_current_user,
        }
    )
    def authenticated_operation(db, config, user, input: str) -> dict:
        """Operation requiring authentication and configuration."""
        try:
            # Check permissions
            if not user.has_permission("query_data"):
                return {"output": None, "error": "Permission denied"}

            # Use config for operation parameters
            if config.debug:
                print(f"Debug: Querying for {input}")

            # Perform database operation
            results = db.query("Data").filter(f"tenant_id = '{config.tenant_id}'").all()

            return {
                "output": results,
                "user": user.username,
                "tenant": config.tenant_id,
                "session": user.session_id,
            }
        finally:
            db.close()

    result = authenticated_operation(input="test_query")

    assert result["user"] == "test_user"
    assert result["tenant"] == "org_test"
    assert result["session"] == "session_123"
    assert len(result["output"]) == 2
    assert _connection_pool.active_connections == 0


def test_bind_with_permission_denied(mock_client):
    """Test that permission checks work correctly with bound auth."""

    def get_unauthorized_user():
        """Get user without required permissions."""
        return AuthContext(
            user_id="user_456",
            username="unauthorized_user",
            roles=["viewer"],  # No query_data permission
            organization_id="org_test",
        )

    @endpoint(bind={"user": get_unauthorized_user})
    def restricted_operation(user, input: str) -> dict:
        """Operation requiring specific permissions."""
        if not user.has_permission("query_data"):
            return {"output": None, "error": "Permission denied"}

        return {"output": "Sensitive data", "user": user.username}

    result = restricted_operation(input="test")

    assert result["output"] is None
    assert result["error"] == "Permission denied"


def test_bind_with_resource_cleanup_on_exception(mock_client):
    """Test that resources are properly cleaned up even on exceptions.

    Uses a generator pattern for bind, which the decorator handles automatically.
    The generator's finally block runs on cleanup, tracking that cleanup occurred.
    """
    cleanup_called = []

    def get_db_with_cleanup():
        """Generator that yields DB session and tracks cleanup via finally block."""
        session = get_db_session()
        try:
            yield session
        finally:
            cleanup_called.append(True)
            session.close()

    @endpoint(bind={"db": get_db_with_cleanup})
    def failing_operation(db, input: str) -> dict:
        """Operation that fails after using resources."""
        # Use the database
        _ = db.query("Data").all()

        # Then fail
        if input == "fail":
            raise RuntimeError("Operation failed")

        return {"output": "success"}

    # Successful case
    result = failing_operation(input="success")
    assert result["output"] == "success"
    assert len(cleanup_called) == 1

    # Failure case - cleanup should still happen
    with pytest.raises(RuntimeError, match="Operation failed"):
        failing_operation(input="fail")

    # Cleanup should have been called twice total
    assert len(cleanup_called) == 2
    assert _connection_pool.active_connections == 0


def test_bind_with_lazy_config_loading(mock_client):
    """Test that config is loaded fresh on each call (useful for hot-reload)."""
    config_load_count = [0]

    def get_fresh_config():
        """Simulate loading config from file/env each time."""
        config_load_count[0] += 1
        return AppConfig(
            debug=config_load_count[0] > 2  # Enable debug after 2 calls
        )

    @endpoint(bind={"config": get_fresh_config})
    def operation_with_config(config, input: str) -> dict:
        """Operation that uses configuration."""
        return {
            "output": f"Processed: {input}",
            "debug_mode": config.debug,
            "config_version": config_load_count[0],
        }

    # Call multiple times
    result1 = operation_with_config(input="test1")
    result2 = operation_with_config(input="test2")
    result3 = operation_with_config(input="test3")

    # Config should be loaded fresh each time
    assert result1["debug_mode"] is False
    assert result1["config_version"] == 1

    assert result2["debug_mode"] is False
    assert result2["config_version"] == 2

    # Debug enabled after 2 calls
    assert result3["debug_mode"] is True
    assert result3["config_version"] == 3


@pytest.mark.asyncio
async def test_bind_with_async_context_manager(mock_client):
    """Test bind with async operations using sync-created session."""

    @endpoint(bind={"db": get_db_session})
    async def async_operation(db, input: str) -> dict:
        """Async operation with database."""
        try:
            # Simulate async operation with the session
            await asyncio.sleep(0.01)
            # Use synchronous query methods (common pattern with SQLAlchemy)
            results = db.query("Data").filter(f"query = '{input}'").all()
            return {"output": results}
        finally:
            db.close()

    result = await async_operation(input="test")

    assert len(result["output"]) == 2
    assert "User from" in result["output"][0]["name"]
    # Connection should be cleaned up
    assert _connection_pool.active_connections == 0

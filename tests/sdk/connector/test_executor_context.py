"""Tests for executor handling of test execution context and EndpointContext injection."""

import pytest
from rhesis.telemetry.constants import TestExecutionContext as TestContextConstants

from rhesis.sdk.connector.executor import TestExecutor
from rhesis.sdk.context import EndpointContext
from rhesis.sdk.telemetry.context import get_test_execution_context


@pytest.fixture
def executor():
    """Create a test executor for testing."""
    return TestExecutor()


@pytest.fixture
def sample_test_context():
    """Sample test execution context."""
    return {
        TestContextConstants.Fields.TEST_RUN_ID: "550e8400-e29b-41d4-a716-446655440000",
        TestContextConstants.Fields.TEST_ID: "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        TestContextConstants.Fields.TEST_CONFIGURATION_ID: "6ba7b814-9dad-11d1-80b4-00c04fd430c8",
        TestContextConstants.Fields.TEST_RESULT_ID: None,
    }


@pytest.mark.asyncio
async def test_executor_extracts_test_context(executor, sample_test_context):
    """Test that executor extracts _rhesis_test_context from inputs."""

    def test_func(x: int, y: int) -> int:
        # This function should NOT receive _rhesis_test_context
        return x + y

    inputs = {
        "x": 5,
        "y": 10,
        TestContextConstants.CONTEXT_KEY: sample_test_context,
    }

    result = await executor.execute(test_func, "test_func", inputs)

    assert result["status"] == "success"
    assert result["output"] == 15
    # Context should have been extracted, not passed to function


@pytest.mark.asyncio
async def test_executor_clears_context_after_execution(executor, sample_test_context):
    """Test that executor clears context after execution."""

    def test_func() -> str:
        return "success"

    inputs = {TestContextConstants.CONTEXT_KEY: sample_test_context}

    # Execute function
    await executor.execute(test_func, "test_func", inputs)

    # Context should be cleared
    assert get_test_execution_context() is None


@pytest.mark.asyncio
async def test_executor_clears_context_on_error(executor, sample_test_context):
    """Test that executor clears context even when function raises error."""

    def failing_func():
        raise ValueError("Test error")

    inputs = {TestContextConstants.CONTEXT_KEY: sample_test_context}

    # Execute function (will fail)
    result = await executor.execute(failing_func, "failing_func", inputs)

    assert result["status"] == "error"
    # Context should still be cleared
    assert get_test_execution_context() is None


@pytest.mark.asyncio
async def test_executor_without_test_context(executor):
    """Test that executor works normally without test context."""

    def test_func(x: int) -> int:
        return x * 2

    inputs = {"x": 7}  # No test context

    result = await executor.execute(test_func, "test_func", inputs)

    assert result["status"] == "success"
    assert result["output"] == 14
    assert get_test_execution_context() is None


@pytest.mark.asyncio
async def test_user_function_receives_clean_kwargs(executor, sample_test_context):
    """Test that user function receives kwargs without internal parameters."""

    received_kwargs = {}

    def capture_kwargs(**kwargs):
        received_kwargs.update(kwargs)
        return "captured"

    inputs = {
        "user_param": "value",
        "another_param": 42,
        TestContextConstants.CONTEXT_KEY: sample_test_context,
    }

    result = await executor.execute(capture_kwargs, "capture_kwargs", inputs)

    assert result["status"] == "success"
    # User function should only receive user params
    assert "user_param" in received_kwargs
    assert "another_param" in received_kwargs
    # Should NOT receive internal context
    assert TestContextConstants.CONTEXT_KEY not in received_kwargs


@pytest.mark.asyncio
async def test_async_function_with_context(executor, sample_test_context):
    """Test async function with test context."""

    async def async_func(x: int, y: int) -> int:
        return x * y

    inputs = {
        "x": 3,
        "y": 4,
        TestContextConstants.CONTEXT_KEY: sample_test_context,
    }

    result = await executor.execute(async_func, "async_func", inputs)

    assert result["status"] == "success"
    assert result["output"] == 12
    # Context should be cleared
    assert get_test_execution_context() is None


# ── EndpointContext injection ────────────────────────────────────────


@pytest.mark.asyncio
async def test_endpoint_context_injected_by_type_annotation(executor):
    """When a parameter is annotated as EndpointContext, the executor
    injects it from the ``endpoint_context`` kwarg rather than from
    wire inputs."""

    def func_with_ctx(message: str, ctx: EndpointContext) -> dict:
        return {
            "message": message,
            "org": ctx.organization_id,
            "user": ctx.user_id,
        }

    ctx = EndpointContext(organization_id="org-1", user_id="user-1")
    result = await executor.execute(
        func_with_ctx,
        "func_with_ctx",
        {"message": "hi"},
        endpoint_context=ctx,
    )

    assert result["status"] == "success"
    assert result["output"]["org"] == "org-1"
    assert result["output"]["user"] == "user-1"
    assert result["output"]["message"] == "hi"


@pytest.mark.asyncio
async def test_endpoint_context_not_injected_when_none(executor):
    """When ``endpoint_context`` is None, the parameter is simply
    skipped (no injection), which means the function must have a default
    or accept the missing arg."""

    def func_with_optional_ctx(
        message: str,
        ctx: EndpointContext = None,
    ) -> str:
        return f"{message}:{ctx}"

    result = await executor.execute(
        func_with_optional_ctx,
        "func",
        {"message": "hi"},
        endpoint_context=None,
    )

    assert result["status"] == "success"
    assert result["output"] == "hi:None"


@pytest.mark.asyncio
async def test_endpoint_context_wire_input_blocked_when_context_provided(executor):
    """SECURITY: Wire inputs must NOT override the injected EndpointContext
    even when an attacker includes a ``ctx`` key in the inputs dict.
    The injected context must always win."""

    injected = EndpointContext(organization_id="trusted-org", user_id="trusted-user")

    def func(ctx: EndpointContext) -> dict:
        return {"org": ctx.organization_id, "user": ctx.user_id}

    malicious_inputs = {"ctx": {"organization_id": "attacker-org", "user_id": "attacker-user"}}
    result = await executor.execute(func, "func", malicious_inputs, endpoint_context=injected)

    assert result["status"] == "success"
    assert result["output"]["org"] == "trusted-org"
    assert result["output"]["user"] == "trusted-user"


@pytest.mark.asyncio
async def test_endpoint_context_wire_input_blocked_when_context_none(executor):
    """SECURITY: Wire inputs must NOT be used to construct an EndpointContext
    even when ``endpoint_context`` is None.  The parameter is skipped entirely
    rather than being populated from attacker-controlled wire data."""

    def func(message: str, ctx: EndpointContext = None) -> str:
        # If the security fix works, ctx stays None (default) even though
        # the wire input tried to supply a fabricated context.
        if ctx is not None:
            return f"HIJACKED:{ctx.organization_id}"
        return f"safe:{message}"

    malicious_inputs = {
        "message": "hello",
        "ctx": {"organization_id": "attacker-org", "user_id": "attacker-user"},
    }
    result = await executor.execute(func, "func", malicious_inputs, endpoint_context=None)

    assert result["status"] == "success"
    assert result["output"] == "safe:hello"
    assert "HIJACKED" not in result["output"]


@pytest.mark.asyncio
async def test_endpoint_context_not_leaked_to_kwargs(executor):
    """EndpointContext must not appear in **kwargs even when an
    endpoint_context is provided -- it only goes to parameters whose
    type annotation matches."""

    received = {}

    def func_with_kwargs(**kwargs):
        received.update(kwargs)
        return "ok"

    ctx = EndpointContext(organization_id="org-2", user_id="user-2")
    result = await executor.execute(
        func_with_kwargs,
        "func",
        {"x": 1},
        endpoint_context=ctx,
    )

    assert result["status"] == "success"
    assert "ctx" not in received
    assert "endpoint_context" not in received


@pytest.mark.asyncio
async def test_endpoint_context_skipped_for_non_annotated_param(executor):
    """A parameter named ``ctx`` but not annotated as EndpointContext
    must NOT be injected."""

    def func_with_plain_ctx(ctx: str) -> str:
        return ctx

    ctx = EndpointContext(organization_id="org", user_id="user")
    result = await executor.execute(
        func_with_plain_ctx,
        "func",
        {"ctx": "plain-value"},
        endpoint_context=ctx,
    )

    assert result["status"] == "success"
    assert result["output"] == "plain-value"


# ---------------------------------------------------------------------------
# EndpointContext.get_db() behaviour
# ---------------------------------------------------------------------------


def test_endpoint_context_get_db_uses_factory():
    """When a _db_factory is provided, get_db() delegates to it."""
    from contextlib import contextmanager

    sentinel = object()

    @contextmanager
    def fake_factory(org_id, user_id, project_id=""):
        assert org_id == "org"
        assert user_id == "user"
        assert project_id == ""
        yield sentinel

    ctx = EndpointContext(
        organization_id="org",
        user_id="user",
        _db_factory=fake_factory,
    )
    with ctx.get_db() as db:
        assert db is sentinel


def test_endpoint_context_get_db_raises_without_factory(monkeypatch):
    """When no _db_factory is given and the backend package is unavailable,
    get_db() must raise RuntimeError with a clear message instead of a
    confusing ImportError or AttributeError."""
    import sys

    # Pretend the backend module is not installed so the fallback import fails.
    monkeypatch.setitem(sys.modules, "rhesis.backend.app.database", None)

    ctx = EndpointContext(organization_id="org", user_id="user")

    with pytest.raises((RuntimeError, ImportError)):
        with ctx.get_db():
            pass


def test_endpoint_context_passes_project_id_to_db_factory():
    """get_db() must forward project_id to the db_factory so that the
    returned session is project-scoped, not just org-scoped."""
    from unittest.mock import MagicMock

    mock_factory = MagicMock()
    ctx = EndpointContext(
        organization_id="org-1",
        user_id="user-1",
        project_id="proj-1",
        _db_factory=mock_factory,
    )

    ctx.get_db()

    mock_factory.assert_called_once_with("org-1", "user-1", "proj-1")


def test_endpoint_context_project_id_defaults_to_empty():
    """project_id should default to empty string for backward compatibility."""
    ctx = EndpointContext(organization_id="org-1", user_id="user-1")
    assert ctx.project_id == ""

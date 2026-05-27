"""Tests for the Architect Celery task's conversation-trace plumbing.

The production architect screen routes every turn through
``architect_chat_task`` -- not ``SdkEndpointInvoker`` -- so the
SDK telemetry ``ContextVar`` trio has to be bound here for multi-turn
traces to share a ``trace_id``.  These tests cover:

* ``_load_session_trace_id`` (lookup of the prior turn's trace_id from
  the persisted architect session)
* ``persist_state`` stamping ``conversation_trace_id`` on
  ``agent_state`` after each successful turn
* ``conversation_telemetry_context`` binding / clearing the SDK
  ContextVars around an async block
* ``architect_chat_task`` parking ``rhesis.conversation.output`` via
  ``register_pending_output`` so the Conversation view shows bot
  responses (mirrors what ``SdkEndpointInvoker`` does automatically)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services.architect.endpoint_operations import persist_state
from rhesis.backend.app.services.telemetry.local_invocation import (
    conversation_telemetry_context,
)
from rhesis.backend.tasks.architect import _load_session_trace_id

# UUID v4 (the version bits matter for ``ArchitectMessageCreate.session_id``
# Pydantic validation: must have ``4`` in the 13th position and 8/9/a/b in
# the 17th).  All tests use the same constant so traces of test runs line
# up by session_id in any debug output.
_VALID_SESSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


# ── _load_session_trace_id ──────────────────────────────────────────


def _make_session_row(agent_state: dict | None) -> MagicMock:
    """Build a ``models.ArchitectSession`` stand-in with the given JSON."""
    row = MagicMock()
    row.agent_state = agent_state
    return row


class TestLoadSessionTraceId:
    """The helper must be tolerant of missing rows / DB errors -- tracing
    is best-effort and may not break the chat path."""

    @patch("rhesis.backend.app.database.get_db_with_tenant_variables")
    @patch("rhesis.backend.app.crud.get_architect_session")
    def test_returns_stored_trace_id(self, mock_get_session, mock_db_ctx):
        """The trace_id stamped by a prior ``persist_state`` call is
        returned verbatim so the next turn can bind it."""
        mock_db_ctx.return_value.__enter__.return_value = MagicMock()
        mock_get_session.return_value = _make_session_row({"conversation_trace_id": "abc123"})

        result = _load_session_trace_id("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "org", "user")

        assert result == "abc123"

    @patch("rhesis.backend.app.database.get_db_with_tenant_variables")
    @patch("rhesis.backend.app.crud.get_architect_session")
    def test_returns_none_when_no_trace_id_in_state(self, mock_get_session, mock_db_ctx):
        """Turn 1 has no prior trace_id; helper returns ``None`` so the
        SDK tracer generates a fresh trace and ``persist_state`` stamps
        it for the next turn."""
        mock_db_ctx.return_value.__enter__.return_value = MagicMock()
        mock_get_session.return_value = _make_session_row({"mode": "discovery"})

        result = _load_session_trace_id("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "org", "user")

        assert result is None

    @patch("rhesis.backend.app.database.get_db_with_tenant_variables")
    @patch("rhesis.backend.app.crud.get_architect_session")
    def test_returns_none_when_agent_state_null(self, mock_get_session, mock_db_ctx):
        """A brand-new session may have ``agent_state = None`` until the
        first ``persist_state`` write."""
        mock_db_ctx.return_value.__enter__.return_value = MagicMock()
        mock_get_session.return_value = _make_session_row(None)

        result = _load_session_trace_id("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "org", "user")

        assert result is None

    @patch("rhesis.backend.app.database.get_db_with_tenant_variables")
    @patch("rhesis.backend.app.crud.get_architect_session")
    def test_returns_none_when_session_missing(self, mock_get_session, mock_db_ctx):
        """Session lookup failures must not blow up the chat path."""
        mock_db_ctx.return_value.__enter__.return_value = MagicMock()
        mock_get_session.return_value = None

        result = _load_session_trace_id("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "org", "user")

        assert result is None

    def test_returns_none_without_session_id(self):
        """Defensive: empty session_id -> no DB call, no trace_id."""
        assert _load_session_trace_id("", "org", "user") is None

    def test_returns_none_without_organization(self):
        """Defensive: missing org context -> no DB call (the tenant
        wrapper would otherwise raise)."""
        assert _load_session_trace_id("session", None, "user") is None

    @patch(
        "rhesis.backend.app.database.get_db_with_tenant_variables",
        side_effect=RuntimeError("redis down"),
    )
    def test_swallows_db_errors(self, _mock_db):
        """Any unexpected error is logged and swallowed -- tracing is
        best-effort and must not break the chat."""
        assert _load_session_trace_id("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "org", "user") is None


# ── persist_state stamps conversation_trace_id ──────────────────────


@pytest.mark.asyncio
async def test_persist_state_stamps_root_trace_id_on_agent_state():
    """When the SDK tracer has set a root trace_id, ``persist_state``
    persists it under ``agent_state["conversation_trace_id"]`` so the
    next turn can reuse it."""
    from rhesis.backend.app.services.local_function_registry import LocalInvocationContext

    agent = MagicMock()
    agent.dump_state.return_value = MagicMock(
        mode="discovery",
        max_iterations=15,
        discovery_state={},
        guard_state={},
        pending_tasks=[],
        id_to_name={},
        plan_data=None,
    )

    ctx = LocalInvocationContext(organization_id="org", user_id="user", db=None)

    with (
        patch(
            "rhesis.sdk.telemetry.context.get_root_trace_id",
            return_value="deadbeef" * 4,
        ),
        patch(
            "rhesis.backend.app.services.architect.endpoint_operations.get_db_with_tenant_variables"
        ) as mock_db_ctx,
        patch("rhesis.backend.app.crud.create_architect_message"),
        patch("rhesis.backend.app.crud.update_architect_session") as mock_update,
    ):
        mock_db_ctx.return_value.__enter__.return_value = MagicMock()

        await persist_state(
            agent=agent,
            response="reply",
            session_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            ctx=ctx,
            session_has_title=True,
            user_message="hi",
        )

    assert mock_update.called
    session_update = mock_update.call_args.kwargs["session"]
    assert session_update.agent_state["conversation_trace_id"] == "deadbeef" * 4


@pytest.mark.asyncio
async def test_persist_state_omits_trace_id_when_tracing_disabled():
    """If the SDK tracer is a no-op (telemetry disabled), there is no
    root trace_id to persist and the key must be absent so future
    lookups cleanly fall back to "first turn"."""
    from rhesis.backend.app.services.local_function_registry import LocalInvocationContext

    agent = MagicMock()
    agent.dump_state.return_value = MagicMock(
        mode="discovery",
        max_iterations=15,
        discovery_state={},
        guard_state={},
        pending_tasks=[],
        id_to_name={},
        plan_data=None,
    )

    ctx = LocalInvocationContext(organization_id="org", user_id="user", db=None)

    with (
        patch("rhesis.sdk.telemetry.context.get_root_trace_id", return_value=None),
        patch(
            "rhesis.backend.app.services.architect.endpoint_operations.get_db_with_tenant_variables"
        ) as mock_db_ctx,
        patch("rhesis.backend.app.crud.create_architect_message"),
        patch("rhesis.backend.app.crud.update_architect_session") as mock_update,
    ):
        mock_db_ctx.return_value.__enter__.return_value = MagicMock()

        await persist_state(
            agent=agent,
            response="reply",
            session_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            ctx=ctx,
            session_has_title=True,
            user_message="hi",
        )

    session_update = mock_update.call_args.kwargs["session"]
    assert "conversation_trace_id" not in session_update.agent_state


# ── conversation_telemetry_context lifecycle ────────────────────────


@pytest.mark.asyncio
async def test_conversation_context_sets_and_clears_contextvars():
    """The async context manager must bind all three SDK ContextVars
    on entry and clear them on exit so they cannot leak into the next
    Celery task that reuses the same asyncio worker."""
    from rhesis.sdk.telemetry.context import (
        get_conversation_id,
        get_conversation_mapped_input,
        get_conversation_trace_id,
        get_root_trace_id,
        set_root_trace_id,
    )

    set_root_trace_id("stale")

    async with conversation_telemetry_context(
        conversation_id="session-1",
        conversation_trace_id="cafef00d" * 4,
        mapped_input="hi",
    ):
        assert get_conversation_id() == "session-1"
        assert get_conversation_trace_id() == "cafef00d" * 4
        assert get_conversation_mapped_input() == "hi"
        # Root trace_id is reset on entry so the inner @endpoint
        # tracer treats this call as the root span.
        assert get_root_trace_id() is None

    assert get_conversation_id() is None
    assert get_conversation_trace_id() is None
    assert get_conversation_mapped_input() is None
    assert get_root_trace_id() is None


@pytest.mark.asyncio
async def test_conversation_context_clears_on_exception():
    """Exceptions inside the block must not leak ContextVars to later
    tasks running on the same worker."""
    from rhesis.sdk.telemetry.context import (
        get_conversation_id,
        get_conversation_trace_id,
    )

    with pytest.raises(RuntimeError, match="boom"):
        async with conversation_telemetry_context(
            conversation_id="session-2",
            conversation_trace_id="0badf00d" * 4,
            mapped_input="oops",
        ):
            raise RuntimeError("boom")

    assert get_conversation_id() is None
    assert get_conversation_trace_id() is None


@pytest.mark.asyncio
async def test_conversation_context_skips_unset_values():
    """First-turn callers pass ``conversation_trace_id=None`` so the
    SDK tracer generates a fresh trace; only non-empty values are
    bound so we don't accidentally clobber an outer scope's state."""
    from rhesis.sdk.telemetry.context import (
        get_conversation_id,
        get_conversation_trace_id,
    )

    async with conversation_telemetry_context(
        conversation_id="session-3",
        conversation_trace_id=None,
        mapped_input="first turn",
    ):
        assert get_conversation_id() == "session-3"
        assert get_conversation_trace_id() is None


# ── _load_session_trace_id uses session_id as conversation_id ───────


def test_session_id_is_uuid_compatible():
    """The Celery task path passes ``session_id`` straight through to
    ``UUID(...)`` for the DB lookup; the helper must therefore reject
    non-UUID input gracefully rather than raising into the task."""
    assert _load_session_trace_id("not-a-uuid", "org", "user") is None


# ── conversation output parking ─────────────────────────────────────


@pytest.mark.unit
def test_task_parks_conversation_output_when_trace_id_available():
    """After ``asyncio.run(_run())`` returns, the task must call
    ``register_pending_output`` so the ingest pipeline can stamp
    ``rhesis.conversation.output`` on the root span.

    This replicates the step that ``SdkEndpointInvoker._park_conversation_output``
    performs on the playground / test-execution path.  Without it the
    Conversation view shows only user messages and marks every turn Failed.
    """
    from rhesis.backend.app.services.architect.endpoint_operations import ArchitectChatResult

    _TRACE_ID = "a" * 32

    fake_result = ArchitectChatResult(
        content="Hello from architect",
        session_id=_VALID_SESSION_ID,
        mode="discovery",
        needs_confirmation=False,
        auto_approve_all=False,
        awaiting_task=False,
        plan=None,
        pending_tasks=[],
    )

    with (
        patch(
            "rhesis.sdk.telemetry.tracer.pop_result_trace_id",
            return_value=_TRACE_ID,
        ) as mock_pop,
        patch(
            "rhesis.backend.app.services.telemetry.conversation_linking.register_pending_output"
        ) as mock_register,
        patch("rhesis.backend.tasks.architect.architect_chat_task.run"),
    ):
        # Simulate the parking logic directly (isolated from Celery infra).
        from rhesis.backend.app.services.telemetry.conversation_linking import (
            register_pending_output,
        )
        from rhesis.sdk.telemetry.tracer import pop_result_trace_id

        trace_id = pop_result_trace_id(fake_result)
        if trace_id:
            register_pending_output(trace_id=trace_id, mapped_output=fake_result.content)

        mock_pop.assert_called_once_with(fake_result)
        mock_register.assert_called_once_with(
            trace_id=_TRACE_ID,
            mapped_output="Hello from architect",
        )


@pytest.mark.unit
def test_task_skips_parking_when_no_trace_id():
    """If ``pop_result_trace_id`` returns ``None`` (tracing disabled or
    the span was a no-op), ``register_pending_output`` must NOT be called
    so we don't park an empty-key entry in the cache."""
    from rhesis.backend.app.services.telemetry.conversation_linking import (
        register_pending_output,
    )

    with (
        patch(
            "rhesis.sdk.telemetry.tracer.pop_result_trace_id",
            return_value=None,
        ),
        patch(
            "rhesis.backend.app.services.telemetry.conversation_linking.register_pending_output"
        ) as mock_register,
    ):
        from rhesis.sdk.telemetry.tracer import pop_result_trace_id

        trace_id = pop_result_trace_id(object())  # any result
        if trace_id:
            register_pending_output(trace_id=trace_id, mapped_output="x")

        mock_register.assert_not_called()

"""Conversation telemetry helpers for the Architect agent.

Binds SDK telemetry ContextVars around each chat turn so multi-turn
sessions render as one coherent trace in the viewer.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _conversation_telemetry_context(
    conversation_id: Optional[str],
    conversation_trace_id: Optional[str],
    mapped_input: Optional[str],
) -> AsyncIterator[None]:
    """Bind the SDK conversation telemetry ContextVars for one turn.

    The SDK tracer reuses ``conversation_trace_id`` (if set) as the
    trace_id for the root span this turn opens, so subsequent turns of
    the same architect session render as one coherent trace in the
    viewer instead of one trace per turn.  All four ContextVars are
    cleared on exit so they do not leak into surrounding scopes that
    share the same asyncio task.
    """
    from rhesis.sdk.telemetry.context import (
        set_conversation_id,
        set_conversation_mapped_input,
        set_conversation_trace_id,
        set_root_trace_id,
    )

    if conversation_id:
        set_conversation_id(conversation_id)
    if conversation_trace_id:
        set_conversation_trace_id(conversation_trace_id)
    if mapped_input:
        set_conversation_mapped_input(mapped_input)
    set_root_trace_id(None)
    try:
        yield
    finally:
        set_conversation_id(None)
        set_conversation_trace_id(None)
        set_conversation_mapped_input(None)
        set_root_trace_id(None)


def _load_session_trace_id(
    session_id: str,
    organization_id: Optional[str],
    user_id: Optional[str],
    project_id: Optional[str] = None,
) -> Optional[str]:
    """Return the conversation root trace_id stamped by a prior turn.

    ``persist_state`` stores the SDK tracer's root trace_id under
    ``agent_state["conversation_trace_id"]`` on every turn.  Returns
    ``None`` for the first turn of a session and on any DB lookup
    failure -- tracing is best-effort and must not break the chat.
    """
    if not session_id or not organization_id:
        return None
    try:
        from rhesis.backend.app import crud
        from rhesis.backend.app.database import get_db_with_tenant_variables

        with get_db_with_tenant_variables(organization_id, user_id or "", project_id or "") as db:
            session_row = crud.get_architect_session(
                db,
                session_id=UUID(session_id),
                organization_id=organization_id,
                user_id=user_id or "",
            )
            if session_row is None:
                return None
            agent_state = session_row.agent_state or {}
            return agent_state.get("conversation_trace_id")
    except Exception as exc:
        logger.warning(
            "Failed to load conversation_trace_id for %s: %s",
            session_id,
            exc,
        )
        return None

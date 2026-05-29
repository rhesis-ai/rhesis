"""Celery task for Architect agent conversations.

Loads session state from DB, runs the ArchitectAgent, streams events
via Redis pub/sub, and persists the final response + updated state.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional
from uuid import UUID

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.publisher import publish_event
from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.worker import app

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

        with get_db_with_tenant_variables(organization_id, user_id or "") as db:
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
        logger.warning("Failed to load conversation_trace_id for %s: %s", session_id, exc)
        return None


@app.task(
    base=SilentTask,
    name="rhesis.backend.tasks.architect.architect_chat_task",
    bind=True,
    max_retries=1,
    soft_time_limit=300,
    time_limit=360,
)
def architect_chat_task(
    self,
    session_id: str,
    user_message: str,
    attachments: Optional[Dict[str, Any]] = None,
    auto_approve: Optional[bool] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Process a single architect chat turn.

    1. Load session from DB (history, plan, mode, agent_state)
    2. Reconstruct ArchitectAgent with saved state
    3. Run agent with WebSocket event handler for streaming
    4. Persist response + updated state to DB
    5. Publish final ARCHITECT_RESPONSE event
    """
    org_id, user_id = self.get_tenant_context()
    channel = f"architect:{session_id}"
    target = ChannelTarget(channel=channel)

    self.log_with_context(
        "info",
        "Starting architect chat task",
        session_id=session_id,
    )

    try:
        import asyncio

        from rhesis.backend.app.database import get_db_with_tenant_variables
        from rhesis.backend.app.services.architect.runner import (
            ArchitectChatResult,
            run_architect_turn,
        )
        from rhesis.sdk.context import EndpointContext

        prior_trace_id = _load_session_trace_id(session_id, org_id, user_id)
        ctx = EndpointContext(
            organization_id=org_id or "",
            user_id=user_id or "",
            _db_factory=get_db_with_tenant_variables,
        )

        async def _run() -> ArchitectChatResult:
            async with _conversation_telemetry_context(
                conversation_id=session_id,
                conversation_trace_id=prior_trace_id,
                mapped_input=user_message,
            ):
                return await run_architect_turn(
                    message=user_message,
                    ctx=ctx,
                    session_id=session_id,
                    attachments=attachments,
                    auto_approve=auto_approve,
                    persist_user_message=False,
                )

        result: ArchitectChatResult = asyncio.run(_run())

        # Park the conversation output so the telemetry ingest pipeline
        # can stamp ``rhesis.conversation.output`` on the root span.
        if result.content:
            try:
                from rhesis.backend.app.services.telemetry.conversation_linking import (
                    register_pending_output,
                )
                from rhesis.sdk.telemetry.tracer import pop_result_trace_id

                turn_trace_id = pop_result_trace_id(result)
                if turn_trace_id:
                    register_pending_output(
                        trace_id=turn_trace_id,
                        mapped_output=result.content,
                    )
                    logger.debug("Parked conversation output for trace_id=%s", turn_trace_id)
            except Exception as exc:
                logger.warning("Failed to park conversation output: %s", exc)

        if result.pending_tasks:
            from rhesis.backend.tasks.architect_monitor import register_awaiting_tasks

            register_awaiting_tasks(
                session_id=session_id,
                task_ids=[t["task_id"] for t in result.pending_tasks],
                org_id=org_id or "",
                user_id=user_id or "",
                auto_approve=result.auto_approve_all,
            )

        publish_event(
            WebSocketMessage(
                type=EventType.ARCHITECT_RESPONSE,
                payload={
                    "session_id": session_id,
                    "content": result.content,
                    "mode": result.mode,
                    "needs_confirmation": result.needs_confirmation,
                    "auto_approve_all": result.auto_approve_all,
                    "awaiting_task": result.awaiting_task,
                    "plan": result.plan,
                },
            ),
            target,
        )

        self.log_with_context(
            "info",
            "Architect chat task completed",
            session_id=session_id,
            response_length=len(result.content),
        )

        return {
            "session_id": session_id,
            "response_length": len(result.content),
            "mode": result.mode,
        }

    except Exception as e:
        logger.error(f"Architect task failed: {e}", exc_info=True)
        publish_event(
            WebSocketMessage(
                type=EventType.ARCHITECT_ERROR,
                payload={
                    "session_id": session_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ),
            target,
        )
        raise


def _process_attachments(
    attachments: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Thin shim preserved for callers outside this module.

    Delegates to the canonical implementation in
    :mod:`rhesis.backend.app.services.architect.attachments`.
    """
    from rhesis.backend.app.services.architect.attachments import process_attachments

    return process_attachments(attachments)

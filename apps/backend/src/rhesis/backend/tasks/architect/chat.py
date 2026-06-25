"""Celery task for Architect agent conversations.

Loads session state from DB, runs the ArchitectAgent, streams events
via Redis pub/sub, and persists the final response + updated state.
"""

import logging
from typing import Any, Dict, Optional

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.publisher import publish_event
from rhesis.backend.tasks.architect.telemetry import (
    _conversation_telemetry_context,
    _load_session_trace_id,
)
from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.worker import app

logger = logging.getLogger(__name__)


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
    _org_id, _user_id, _project_id = self.get_tenant_context()
    org_id = _org_id or ""
    user_id = _user_id or ""
    project_id = _project_id or ""
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

        prior_trace_id = _load_session_trace_id(session_id, org_id, user_id, project_id)
        ctx = EndpointContext(
            organization_id=org_id,
            user_id=user_id,
            project_id=project_id,
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
                    project_id=project_id,
                )

        result: ArchitectChatResult = asyncio.run(_run())

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
                    logger.debug(
                        "Parked conversation output for trace_id=%s",
                        turn_trace_id,
                    )
            except Exception as exc:
                logger.warning("Failed to park conversation output: %s", exc)

        if result.pending_tasks:
            from rhesis.backend.tasks.architect.monitor import (
                register_awaiting_tasks,
            )

            register_awaiting_tasks(
                session_id=session_id,
                task_ids=[t["task_id"] for t in result.pending_tasks],
                org_id=org_id,
                user_id=user_id,
                auto_approve=result.auto_approve_all,
                project_id=project_id,
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

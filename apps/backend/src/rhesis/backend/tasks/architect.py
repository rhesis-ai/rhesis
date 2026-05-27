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

        from rhesis.backend.app.services.architect.endpoint_operations import (
            ArchitectChatResult,
            architect_chat,
        )
        from rhesis.backend.app.services.local_function_registry import LocalInvocationContext

        ctx = LocalInvocationContext(
            organization_id=org_id or "",
            user_id=user_id or None,
            db=None,
        )
        result: ArchitectChatResult = asyncio.run(
            architect_chat(
                message=user_message,
                ctx=ctx,
                session_id=session_id,
                attachments=attachments,
                auto_approve=auto_approve,
                persist_user_message=False,
            )
        )

        if result.pending_tasks:
            from rhesis.backend.tasks.architect_monitor import (
                register_awaiting_tasks,
            )

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

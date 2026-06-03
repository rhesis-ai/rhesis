"""Architect message handler for the WebSocket layer.

Receives ARCHITECT_MESSAGE events from the frontend, persists the user
message, and dispatches a Celery task for the agent to process it.
Streaming events flow back via Redis pub/sub → ChannelTarget.
"""

import logging
from typing import TYPE_CHECKING

from rhesis.backend.app.database import bind_scope_to_session, get_db_with_tenant_variables
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.websocket import (
    ConnectionTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.scope import bypass_tenant_filter

if TYPE_CHECKING:
    from rhesis.backend.app.services.websocket.manager import WebSocketManager

logger = logging.getLogger(__name__)


async def handle_architect_message(
    manager: "WebSocketManager",
    conn_id: str,
    user: User,
    message: WebSocketMessage,
) -> None:
    """Handle an incoming architect chat message.

    1. Validate payload (session_id, message)
    2. Persist user message to DB
    3. Dispatch Celery task for agent processing
    4. Return acknowledgement to client

    Streaming events arrive via Redis pub/sub on channel
    ``architect:{session_id}`` and are forwarded by the WS manager
    to clients subscribed to that channel.
    """
    correlation_id = message.correlation_id
    payload = message.payload or {}

    session_id = payload.get("session_id")
    user_message = payload.get("message")

    if not session_id:
        await _send_architect_error(
            manager, conn_id, correlation_id, "Missing session_id in payload"
        )
        return

    if not user_message:
        await _send_architect_error(manager, conn_id, correlation_id, "Missing message in payload")
        return

    logger.info(
        "Architect message from conn=%s session=%s (len=%d)",
        conn_id,
        session_id,
        len(user_message),
    )

    try:
        from uuid import UUID

        from rhesis.backend.app import crud, schemas

        with get_db_with_tenant_variables(str(user.organization_id), str(user.id)) as db:
            # Bypass project filter to find sessions regardless of their project_id.
            # We verify org ownership explicitly; the session's own project_id is
            # then used to scope the Celery task.
            with bypass_tenant_filter():
                db_session = crud.get_architect_session(
                    db,
                    session_id=UUID(session_id),
                    organization_id=str(user.organization_id),
                    user_id=str(user.id),
                )
            if not db_session:
                await _send_architect_error(
                    manager, conn_id, correlation_id, "Session not found or access denied"
                )
                return

            # Carry the session's project_id so the Celery task scopes its DB sessions
            # correctly, even when the WebSocket connection has no project context.
            active_project_id = str(db_session.project_id) if db_session.project_id else None

            # Persist user message with the correct project scope if known.
            session_project_id = active_project_id or ""
            bind_scope_to_session(
                db,
                str(user.organization_id),
                str(user.id),
                session_project_id,
            )
            crud.create_architect_message(
                db=db,
                message=schemas.ArchitectMessageCreate(
                    session_id=session_id,
                    role="user",
                    content=user_message,
                    attachments=payload.get("attachments"),
                ),
                organization_id=str(user.organization_id),
                user_id=str(user.id),
            )

        # Dispatch Celery task
        from rhesis.backend.tasks.architect import architect_chat_task

        task_headers = {
            "organization_id": str(user.organization_id),
            "user_id": str(user.id),
        }
        if active_project_id:
            task_headers["project_id"] = active_project_id

        architect_chat_task.apply_async(
            kwargs={
                "session_id": session_id,
                "user_message": user_message,
                "attachments": payload.get("attachments"),
                "auto_approve": payload.get("auto_approve"),
            },
            headers=task_headers,
        )

        # Acknowledge receipt
        await manager.broadcast(
            WebSocketMessage(
                type=EventType.ARCHITECT_THINKING,
                correlation_id=correlation_id,
                channel=f"architect:{session_id}",
                payload={"status": "processing", "session_id": session_id},
            ),
            ConnectionTarget(connection_id=conn_id),
        )

    except Exception as e:
        logger.error(f"Error handling architect message: {e}", exc_info=True)
        await _send_architect_error(
            manager,
            conn_id,
            correlation_id,
            str(e),
            error_type=type(e).__name__,
        )


async def _send_architect_error(
    manager: "WebSocketManager",
    conn_id: str,
    correlation_id: str | None,
    error_message: str,
    error_type: str = "Error",
) -> None:
    await manager.broadcast(
        WebSocketMessage(
            type=EventType.ARCHITECT_ERROR,
            correlation_id=correlation_id,
            payload={
                "error": error_message,
                "error_type": error_type,
            },
        ),
        ConnectionTarget(connection_id=conn_id),
    )

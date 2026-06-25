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
    # The frontend sends the session's own project_id (not the currently active
    # project cookie) so the DB lookup can satisfy the project_isolation RLS
    # policy. These two values can differ when the user switches projects after
    # creating the session, which previously caused "Session not found" errors.
    client_project_id = payload.get("project_id") or ""

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

        with get_db_with_tenant_variables(
            str(user.organization_id), str(user.id), client_project_id
        ) as db:
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

            # Carry the session's project_id so the Celery task scopes its DB
            # sessions correctly, even when the WebSocket payload had no project.
            active_project_id = str(db_session.project_id) if db_session.project_id else None

            # Ensure the DB scope (GUC + auto-stamp) uses the session's own project,
            # not the client-supplied project. If the two differ (e.g. user switched
            # active project after creating the session), the auto-stamp would write
            # project_id = session.project_id while app.current_project = client_project,
            # causing a project_isolation RLS violation on the INSERT.
            if active_project_id and active_project_id != client_project_id:
                bind_scope_to_session(
                    db,
                    str(user.organization_id),
                    str(user.id),
                    active_project_id,
                )

            # SP11: gate the message → agent-run enqueue through the PDP. The WS
            # transport is not covered by the HTTP PEP backstop, so authorize
            # explicitly here. Reuse the connection's stored principal (carries
            # token scopes + project boundary from auth) so scoped tokens and
            # read-only roles cannot trigger agent execution.
            from rhesis.backend.app.auth.capabilities import Permission
            from rhesis.backend.app.auth.principal import resolve_principal
            from rhesis.backend.app.auth.rbac import authorize

            principal = manager._principals.get(conn_id) or resolve_principal(user)
            authz_project_id = UUID(active_project_id) if active_project_id else None
            if not authorize(
                principal, Permission.Architect.CREATE, project_id=authz_project_id, db=db
            ):
                await _send_architect_error(
                    manager,
                    conn_id,
                    correlation_id,
                    "Not authorized to send messages in this architect session",
                )
                return

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

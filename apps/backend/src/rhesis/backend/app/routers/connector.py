"""Connector router for bidirectional communication with SDKs."""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from rhesis.backend.app.routers.base import RhesisRouter
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import authenticate_websocket, require_current_user_or_token
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.connector import (
    ConnectionStatusResponse,
    ExecutionTrace,
    TraceResponse,
    TriggerTestRequest,
    TriggerTestResponse,
)
from rhesis.backend.app.services.connector.manager import connection_manager
from rhesis.backend.app.services.connector.schemas import (
    WebSocketConnectionContext,
)

logger = logging.getLogger(__name__)

router = RhesisRouter(prefix="/connector", tags=["connector"], resource="connector")


def _assert_project_membership(db: Session, project_id_str: str, user: User) -> None:
    """Raise 400 or 403 if *user* is not a member of the project.

    Mirrors the membership check in ``get_project_context`` (dependencies.py)
    so that connector endpoints enforce the same project-isolation guarantee as
    the rest of the API.
    """
    try:
        project_uuid = uuid.UUID(project_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id: must be a UUID")

    membership = (
        db.query(ProjectMembership)
        .filter_by(
            project_id=project_uuid,
            user_id=user.id,
            organization_id=user.organization_id,
        )
        .first()
    )
    project = db.query(Project).filter_by(id=project_uuid).first()
    if not membership or project is None:
        raise HTTPException(
            status_code=403,
            detail=f"User is not a member of project {project_id_str}",
        )


# --- Security limits (configurable via env) ---
MAX_MESSAGE_SIZE = int(os.getenv("WS_MAX_MESSAGE_SIZE", str(1024 * 1024)))
IDLE_TIMEOUT = int(os.getenv("WS_IDLE_TIMEOUT", "300"))
RATE_LIMIT_PER_SECOND = int(os.getenv("WS_RATE_LIMIT", "50"))


async def require_websocket_user(websocket: WebSocket) -> tuple[User, str | None]:
    """FastAPI dependency that authenticates a WebSocket connection.

    Extracts the Bearer token, validates it, and returns the authenticated
    User together with the token's scoped project_id (if any).
    Closes the WebSocket with code 1008 if authentication fails.
    """
    try:
        return await authenticate_websocket(websocket)
    except HTTPException as e:
        await websocket.close(code=1008, reason=str(e.detail))
        raise


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    auth: tuple[User, str | None] = Depends(require_websocket_user),
):
    """WebSocket endpoint for SDK connections.

    The connection is authenticated via Bearer token only. Project and
    environment binding happens later when the SDK sends a ``register``
    message. This allows the same connection to serve both project-scoped
    operations (endpoint execution, traces) and project-less operations
    (standalone metric evaluation).
    """
    user, token_project_id = auth
    context = WebSocketConnectionContext(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        token_project_id=token_project_id,
    )
    logger.info(
        f"WebSocket authenticated: user={user.email}, connection_id={context.connection_id}"
    )

    await websocket.accept()

    try:
        await connection_manager.connect(context.connection_id, context, websocket)

        await websocket.send_json(
            {
                "type": "connected",
                "status": "success",
                "connection_id": context.connection_id,
                "organization_id": context.organization_id,
                "user_id": context.user_id,
            }
        )

        await _message_loop(websocket, context)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {context.connection_id}")

    except Exception as e:
        logger.error(f"WebSocket error for {context.connection_id}: {e}")

    finally:
        connection_manager.disconnect_by_connection_id(context.connection_id)


async def _message_loop(
    websocket: WebSocket,
    context: WebSocketConnectionContext,
) -> None:
    """Listen for messages and dispatch to the connection manager.

    Security measures applied per-message:
    - **Size limit**: rejects payloads larger than ``MAX_MESSAGE_SIZE``.
    - **Idle timeout**: closes connection after ``IDLE_TIMEOUT`` seconds
      of inactivity.
    - **Rate limiting**: drops messages exceeding ``RATE_LIMIT_PER_SECOND``
      per sliding window.
    - **Malformed JSON**: sends an error back and continues.
    """
    msg_timestamps: list[float] = []

    while True:
        try:
            data = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=IDLE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Idle timeout ({IDLE_TIMEOUT}s) for {context.connection_id}")
            await websocket.close(code=1000, reason="Idle timeout")
            return

        # --- Message size limit ---
        if len(data) > MAX_MESSAGE_SIZE:
            logger.warning(f"Oversized message ({len(data)} bytes) from {context.connection_id}")
            await websocket.send_json(
                {
                    "type": "error",
                    "detail": (f"Message too large (max {MAX_MESSAGE_SIZE} bytes)"),
                }
            )
            continue

        # --- Rate limiting (sliding window) ---
        now = time.monotonic()
        msg_timestamps = [t for t in msg_timestamps if now - t < 1.0]
        if len(msg_timestamps) >= RATE_LIMIT_PER_SECOND:
            logger.warning(f"Rate limit exceeded for {context.connection_id}")
            await websocket.send_json(
                {
                    "type": "error",
                    "detail": "Rate limit exceeded",
                }
            )
            continue
        msg_timestamps.append(now)

        # --- JSON parsing ---
        try:
            message: Dict[str, Any] = json.loads(data)
        except json.JSONDecodeError:
            await websocket.send_json(
                {
                    "type": "error",
                    "detail": "Invalid JSON",
                }
            )
            continue

        # Resolve the project_id for this message so the DB session scope
        # matches the actual project.  Without this, auto_filter appends
        # "WHERE project_id IS NULL" to every query on the session, which
        # conflicts with the explicit "WHERE project_id = ?" filters in
        # sync_sdk_endpoints/test_result handlers and returns zero rows.
        #
        # - register:    project_id is in the message payload itself.
        # - all others:  the connection is already bound to a project after
        #   the register handshake; resolve it from the routing table.
        message_type = message.get("type")
        if message_type == "register":
            scope_project_id = message.get("project_id") or ""
        else:
            scope_project_id, _ = connection_manager._resolve_project_for_connection(
                context.connection_id
            )

        with get_db_with_tenant_variables(
            context.organization_id, context.user_id, scope_project_id
        ) as db:
            response = await connection_manager.handle_message(
                connection_id=context.connection_id,
                message=message,
                db=db,
                organization_id=context.organization_id,
                user_id=context.user_id,
            )

        if response:
            await websocket.send_json(response)


@router.post("/trigger", response_model=TriggerTestResponse)
async def trigger_test(
    request: TriggerTestRequest,
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Trigger a test execution via WebSocket.

    The caller must be authenticated and the project must belong to their
    organization.  This prevents unauthenticated or cross-tenant triggering.

    Args:
        request: Test trigger request
        current_user: Authenticated user (from Bearer token / API key)

    Returns:
        Test trigger response

    Raises:
        HTTPException: 400 if project_id is not a valid UUID
        HTTPException: 404 if project is not accessible or not connected
        HTTPException: 500 if sending the request to the SDK fails
    """
    organization_id = str(current_user.organization_id)
    user_id = str(current_user.id)

    # Validate project membership before touching the connection layer.
    with get_db_with_tenant_variables(organization_id, user_id, "") as db:
        _assert_project_membership(db, request.project_id, current_user)

    # Check for a LOCAL connection only — send_test_request() cannot route to
    # remote instances.  is_connected() is Redis-aware and would return True for
    # a project connected to a different backend pod, leading to a misleading 500.
    if not connection_manager.has_local_route(request.project_id, request.environment):
        raise HTTPException(
            status_code=404,
            detail=f"Project {request.project_id} ({request.environment}) not connected",
        )

    # Generate test run ID
    test_run_id = f"test_{uuid.uuid4().hex[:12]}"

    # Send test request
    success = await connection_manager.send_test_request(
        project_id=request.project_id,
        environment=request.environment,
        test_run_id=test_run_id,
        function_name=request.function_name,
        inputs=request.inputs,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send test request to SDK")

    return TriggerTestResponse(
        success=True,
        test_run_id=test_run_id,
        message=f"Test execution requested for {request.function_name}",
    )


@router.get("/status/{project_id}", response_model=ConnectionStatusResponse)
def get_status(
    project_id: str,
    environment: str = "development",
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get connection status for a project.

    The caller must be authenticated and a member of the requested project.

    Args:
        project_id: Project identifier
        environment: Environment name
        current_user: Authenticated user (from Bearer token / API key)

    Returns:
        Connection status
    """
    organization_id = str(current_user.organization_id)
    user_id = str(current_user.id)

    with get_db_with_tenant_variables(organization_id, user_id, "") as db:
        _assert_project_membership(db, project_id, current_user)

    status = connection_manager.get_connection_status(project_id, environment)
    return status


@router.post("/trace", response_model=TraceResponse)
def receive_trace(
    trace: ExecutionTrace,
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Receive execution trace from SDK.

    This endpoint receives traces for all normal executions of
    decorated functions (observability). The caller must be authenticated
    and a member of the project the trace belongs to.

    Args:
        trace: Execution trace data
        current_user: Authenticated user (from Bearer token / API key)

    Returns:
        Success response
    """
    organization_id = str(current_user.organization_id)
    user_id = str(current_user.id)

    with get_db_with_tenant_variables(organization_id, user_id, "") as db:
        _assert_project_membership(db, trace.project_id, current_user)

    logger.info("=" * 80)
    logger.info("📊 EXECUTION TRACE RECEIVED")
    logger.info(f"Project: {trace.project_id}:{trace.environment}")
    logger.info(f"Function: {trace.function_name}")
    logger.info(f"Status: {trace.status}")
    logger.info(f"Duration: {trace.duration_ms:.2f}ms")

    if trace.status == "success":
        if trace.output:
            output_str = str(trace.output)
            if len(output_str) > 200:
                logger.info(f"Output (truncated): {output_str[:200]}...")
            else:
                logger.info(f"Output: {output_str}")
    else:
        logger.error(f"Error: {trace.error}")

    logger.info("=" * 80)

    # TODO: Store trace in database for analytics
    # For now, traces are logged

    return TraceResponse(status="received")

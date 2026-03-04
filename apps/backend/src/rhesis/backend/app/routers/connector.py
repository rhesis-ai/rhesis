"""Connector router for bidirectional communication with SDKs."""

import json
import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from rhesis.backend.app.auth.user_utils import authenticate_websocket
from rhesis.backend.app.database import get_db_with_tenant_variables
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

router = APIRouter(prefix="/connector", tags=["connector"])


async def require_websocket_user(websocket: WebSocket) -> User:
    """FastAPI dependency that authenticates a WebSocket connection.

    Extracts the Bearer token, validates it, and returns the authenticated
    User. Closes the WebSocket with code 1008 if authentication fails.
    """
    try:
        return await authenticate_websocket(websocket)
    except HTTPException as e:
        await websocket.close(code=1008, reason=str(e.detail))
        raise


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user: User = Depends(require_websocket_user),
):
    """WebSocket endpoint for SDK connections.

    The connection is authenticated via Bearer token only. Project and
    environment binding happens later when the SDK sends a ``register``
    message. This allows the same connection to serve both project-scoped
    operations (endpoint execution, traces) and project-less operations
    (standalone metric evaluation).
    """
    context = WebSocketConnectionContext(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
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

    Catches JSON decode errors per-message so a single malformed message
    does not kill the connection.
    """
    while True:
        data = await websocket.receive_text()

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

        with get_db_with_tenant_variables(context.organization_id, context.user_id) as db:
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
async def trigger_test(request: TriggerTestRequest):
    """
    Trigger a test execution via WebSocket.

    Args:
        request: Test trigger request

    Returns:
        Test trigger response

    Raises:
        HTTPException: If project not connected or error sending request
    """
    # Check if connected (checks local + Redis for multi-instance support)
    is_connected = await connection_manager.is_connected(request.project_id, request.environment)
    if not is_connected:
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
async def get_status(project_id: str, environment: str = "development"):
    """
    Get connection status for a project.

    Args:
        project_id: Project identifier
        environment: Environment name

    Returns:
        Connection status
    """
    status = connection_manager.get_connection_status(project_id, environment)
    return status


@router.post("/trace", response_model=TraceResponse)
async def receive_trace(trace: ExecutionTrace):
    """
    Receive execution trace from SDK.

    This endpoint receives traces for all normal executions of
    decorated functions (observability).

    Args:
        trace: Execution trace data

    Returns:
        Success response
    """
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

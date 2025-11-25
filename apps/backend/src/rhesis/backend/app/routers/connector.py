"""Connector router for bidirectional communication with SDKs."""

import json
import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from rhesis.backend.app.auth.user_utils import authenticate_websocket
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.schemas.connector import (
    ConnectionStatusResponse,
    ExecutionTrace,
    TraceResponse,
    TriggerTestRequest,
    TriggerTestResponse,
)
from rhesis.backend.app.services.connector.manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connector", tags=["connector"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for SDK connections.

    Handles:
    - Connection authentication
    - Function registration
    - Test execution requests
    - Bidirectional communication
    """
    logger.info("WebSocket connection attempt received")

    # Authenticate the connection
    try:
        user = await authenticate_websocket(websocket)
        logger.info(f"WebSocket authenticated for user: {user.email}")
    except HTTPException as e:
        logger.error(f"Authentication failed: {e.detail}")
        await websocket.close(code=1008, reason=str(e.detail))
        return

    # Validate additional headers
    project_id = websocket.headers.get("x-rhesis-project", "")
    environment = websocket.headers.get("x-rhesis-environment", "development")

    if not project_id:
        logger.error("Missing project_id in WebSocket headers")
        await websocket.close(code=1008, reason="Missing project_id")
        return

    # Accept connection after all validation passes
    await websocket.accept()
    logger.info(f"WebSocket accepted: {project_id}:{environment}")

    # Get tenant context
    organization_id = str(user.organization_id)
    user_id = str(user.id)

    try:
        # Register connection
        await connection_manager.connect(project_id, environment, websocket)

        # Send acknowledgment
        await websocket.send_json({"type": "connected", "status": "success"})

        # Listen for messages
        while True:
            # Receive message
            data = await websocket.receive_text()
            message: Dict[str, Any] = json.loads(data)

            # Handle message via connection manager
            with get_db_with_tenant_variables(organization_id, user_id) as db:
                response = await connection_manager.handle_message(
                    project_id=project_id,
                    environment=environment,
                    message=message,
                    db=db,
                    organization_id=organization_id,
                    user_id=user_id,
                )

            # Send response if provided
            if response:
                await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {project_id}:{environment}")

    except Exception as e:
        logger.error(f"WebSocket error for {project_id}:{environment}: {e}")

    finally:
        # Clean up connection
        if project_id:
            connection_manager.disconnect(project_id, environment)


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
    # Check if connected
    if not connection_manager.is_connected(request.project_id, request.environment):
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

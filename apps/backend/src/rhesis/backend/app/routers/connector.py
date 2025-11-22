"""Connector router for bidirectional communication with SDKs."""

import json
import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials

from rhesis.backend.app.auth.token_utils import get_secret_key
from rhesis.backend.app.auth.user_utils import get_authenticated_user_with_context
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
    logger.info("=" * 80)
    logger.info("WebSocket connection attempt received")

    # Extract auth header
    auth_header = websocket.headers.get("authorization", "")
    logger.info(f"Auth header present: {bool(auth_header)}")

    if auth_header:
        # Log first 20 chars of header for debugging (don't log full token)
        logger.info(f"Auth header prefix: {auth_header[:20]}...")

    if not auth_header.startswith("Bearer "):
        logger.error("Missing or invalid authorization header")
        await websocket.close(code=1008, reason="Missing authorization")
        return

    token_value = auth_header.replace("Bearer ", "")
    logger.info(f"Token extracted, starts with: {token_value[:10]}...")
    logger.info(f"Token format valid (starts with rh-): {token_value.startswith('rh-')}")

    # Create credentials object and mock request to use existing auth utilities
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_value)

    # Create a mock request object with minimal required attributes
    class MockRequest:
        def __init__(self):
            self.session = {}
            self.state = type("obj", (object,), {})()

    mock_request = MockRequest()
    logger.info("Mock request created")

    # Use the existing authentication utility
    try:
        logger.info("Getting secret key...")
        secret_key = get_secret_key()
        logger.info(f"Secret key obtained: {bool(secret_key)}")

        logger.info("Calling get_authenticated_user_with_context...")
        user = await get_authenticated_user_with_context(
            request=mock_request,
            credentials=credentials,
            secret_key=secret_key,
            without_context=True,  # Allow users without organization for SDK connections
        )

        logger.info(f"Authentication result - User found: {user is not None}")

        if not user:
            logger.error("Authentication failed - no user returned")
            await websocket.close(code=1008, reason="Invalid token")
            return

        logger.info(f"Token validated successfully for user: {user.email}")
        logger.info("=" * 80)

    except HTTPException as e:
        logger.error(f"HTTPException during authentication: {e.status_code} - {e.detail}")
        await websocket.close(code=1008, reason=str(e.detail))
        return
    except Exception as e:
        logger.error(f"Unexpected exception during authentication: {type(e).__name__} - {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        await websocket.close(code=1008, reason="Authentication failed")
        return

    # Accept connection after successful authentication
    logger.info("Accepting WebSocket connection...")
    await websocket.accept()
    logger.info("WebSocket connection accepted successfully")

    project_id: str = ""
    environment: str = ""

    try:
        # Get connection info from headers
        project_id = websocket.headers.get("x-rhesis-project", "")
        environment = websocket.headers.get("x-rhesis-environment", "development")

        if not project_id:
            logger.error("Missing project_id in WebSocket headers")
            await websocket.close(code=1008, reason="Missing project_id")
            return

        # Register connection
        await connection_manager.connect(project_id, environment, websocket)
        logger.info(f"WebSocket connected: {project_id}:{environment}")

        # Send acknowledgment
        await websocket.send_json({"type": "connected", "status": "success"})

        # Listen for messages
        while True:
            # Receive message
            data = await websocket.receive_text()
            message: Dict[str, Any] = json.loads(data)

            message_type = message.get("type")
            logger.info(f"Received message type: {message_type} from {project_id}")

            if message_type == "register":
                # Handle registration
                await connection_manager.handle_registration(project_id, environment, message)
                await websocket.send_json({"type": "registered", "status": "success"})

            elif message_type == "test_result":
                # Handle test result
                test_run_id = message.get("test_run_id")
                status = message.get("status")
                output = message.get("output")
                error = message.get("error")
                duration_ms = message.get("duration_ms")

                logger.info("=" * 80)
                logger.info("📥 TEST RESULT RECEIVED")
                logger.info(f"Project: {project_id}:{environment}")
                logger.info(f"Test Run ID: {test_run_id}")
                logger.info(f"Status: {status}")
                logger.info(f"Duration: {duration_ms}ms")

                if status == "success":
                    # Log output (truncate if too long)
                    output_str = str(output)
                    if len(output_str) > 500:
                        logger.info(f"Output (first 500 chars): {output_str[:500]}...")
                        logger.info(f"Output (last 100 chars): ...{output_str[-100:]}")
                    else:
                        logger.info(f"Output: {output_str}")
                else:
                    logger.error(f"Error: {error}")

                logger.info("=" * 80)

                # TODO: Store test result in database
                # For now, results are logged

            elif message_type == "pong":
                # Pong response
                logger.debug(f"Received pong from {project_id}")

            else:
                logger.warning(f"Unknown message type: {message_type}")

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

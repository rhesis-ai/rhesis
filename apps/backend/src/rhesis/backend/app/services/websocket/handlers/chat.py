"""Chat message handler for the Playground feature.

This module handles chat messages from the frontend playground,
invoking endpoints and returning responses with trace information.
"""

import logging
from typing import TYPE_CHECKING

from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.websocket import (
    ConnectionTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.endpoint import EndpointService
from rhesis.backend.app.services.invokers.common.schemas import ErrorResponse
from rhesis.backend.app.services.invokers.conversation import CONVERSATION_FIELD_NAMES

if TYPE_CHECKING:
    from rhesis.backend.app.services.websocket.manager import WebSocketManager

logger = logging.getLogger(__name__)


async def handle_chat_message(
    manager: "WebSocketManager",
    conn_id: str,
    user: User,
    message: WebSocketMessage,
) -> None:
    """Handle a chat message from the playground.

    This handler:
    1. Extracts endpoint_id and message from payload
    2. Invokes the endpoint via EndpointService
    3. Returns the response with trace_id for trace viewing

    Expected payload:
        {
            "endpoint_id": "uuid-of-endpoint",
            "message": "User's message to the endpoint",
            "session_id": "optional-session-id"  # Also accepts: conversation_id, thread_id, chat_id
        }

    Response payload (CHAT_RESPONSE):
        {
            "output": "Endpoint's response",
            "trace_id": "uuid-of-trace",
            "endpoint_id": "uuid-of-endpoint",
            "session_id": "session-id-from-endpoint"  # Canonical name for session tracking
        }

    Error payload (CHAT_ERROR):
        {
            "error": "Error message",
            "error_type": "ErrorClassName"
        }

    Args:
        manager: The WebSocketManager instance for sending responses.
        conn_id: The connection ID to respond to.
        user: The authenticated user making the request.
        message: The incoming chat message.
    """
    correlation_id = message.correlation_id
    payload = message.payload or {}

    # Extract required fields
    endpoint_id = payload.get("endpoint_id")
    user_message = payload.get("message")

    if not endpoint_id:
        await _send_chat_error(manager, conn_id, correlation_id, "Missing endpoint_id in payload")
        return

    if not user_message:
        await _send_chat_error(manager, conn_id, correlation_id, "Missing message in payload")
        return

    logger.info(
        f"Chat message from conn={conn_id} to endpoint={endpoint_id}: {user_message[:100]}..."
    )

    try:
        # Get database session
        with get_db() as db:
            # Create endpoint service and invoke
            endpoint_service = EndpointService()

            # Prepare input data for the endpoint
            input_data = {
                "input": user_message,
            }

            # Extract session tracking ID from any recognized field name
            # (conversation_id, session_id, thread_id, chat_id, etc.)
            # This makes the API flexible for different client conventions.
            session_id = None
            for field in CONVERSATION_FIELD_NAMES:
                if payload.get(field):
                    session_id = payload.get(field)
                    logger.debug(f"Extracted session ID from payload field '{field}': {session_id}")
                    break

            if session_id:
                # Use session_id as the canonical internal name
                # The endpoint's request_mapping should use {{ session_id }}
                input_data["session_id"] = session_id

            # Invoke the endpoint
            result = await endpoint_service.invoke_endpoint(
                db=db,
                endpoint_id=endpoint_id,
                input_data=input_data,
                organization_id=str(user.organization_id),
                user_id=str(user.id),
            )

            # Check if the result is an error response
            if isinstance(result, ErrorResponse):
                # The endpoint returned an error - send as chat error
                await _send_chat_error(
                    manager,
                    conn_id,
                    correlation_id,
                    result.output,
                    error_type=result.error_type,
                )
                return

            # Extract output and trace_id from result dict
            output = result.get("output", "")
            trace_id = result.get("trace_id")

            # Build response payload
            response_payload = {
                "output": output,
                "trace_id": trace_id,
                "endpoint_id": endpoint_id,
            }

            # Extract session ID from response
            # Primary: Use canonical session_id from response_mapping
            # Fallback: Check other recognized field names for backward compatibility
            response_session_id = result.get("session_id")
            if not response_session_id:
                # Fallback for endpoints without proper response_mapping
                for field in CONVERSATION_FIELD_NAMES:
                    if result.get(field):
                        response_session_id = result.get(field)
                        logger.debug(
                            f"Fallback: extracted session ID from response field '{field}'"
                        )
                        break

            # Include session_id in response (canonical name)
            # Use response value if found, otherwise echo back input session_id
            if response_session_id:
                response_payload["session_id"] = response_session_id
            elif session_id:
                response_payload["session_id"] = session_id

            # Send successful response
            await manager.broadcast(
                WebSocketMessage(
                    type=EventType.CHAT_RESPONSE,
                    correlation_id=correlation_id,
                    payload=response_payload,
                ),
                ConnectionTarget(connection_id=conn_id),
            )

            logger.info(
                f"Chat response sent to conn={conn_id}, "
                f"trace_id={trace_id}, session_id={response_payload.get('session_id')}"
            )

    except Exception as e:
        logger.error(
            f"Error invoking endpoint {endpoint_id} for chat: {e}",
            exc_info=True,
        )
        await _send_chat_error(
            manager,
            conn_id,
            correlation_id,
            str(e),
            error_type=type(e).__name__,
        )


async def _send_chat_error(
    manager: "WebSocketManager",
    conn_id: str,
    correlation_id: str | None,
    error_message: str,
    error_type: str = "Error",
) -> None:
    """Send a chat error response.

    Args:
        manager: The WebSocketManager instance.
        conn_id: The connection ID to respond to.
        correlation_id: The correlation ID from the request.
        error_message: The error message to send.
        error_type: The type/class of the error.
    """
    await manager.broadcast(
        WebSocketMessage(
            type=EventType.CHAT_ERROR,
            correlation_id=correlation_id,
            payload={
                "error": error_message,
                "error_type": error_type,
            },
        ),
        ConnectionTarget(connection_id=conn_id),
    )

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
            "conversation_id": "optional-conversation-id"
        }

    Response payload (CHAT_RESPONSE):
        {
            "output": "Endpoint's response",
            "trace_id": "uuid-of-trace",
            "endpoint_id": "uuid-of-endpoint",
            "conversation_id": "optional-conversation-id-from-endpoint"
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

            # Include conversation_id if provided (for multi-turn)
            conversation_id = payload.get("conversation_id")
            if conversation_id:
                input_data["conversation_id"] = conversation_id

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

            # Get conversation_id from result - the invoker's ConversationTracker
            # already handles extracting/adding conversation tracking fields to the response.
            # Check common field names (conversation_id, session_id, thread_id, chat_id).
            response_conversation_id = (
                result.get("conversation_id")
                or result.get("session_id")
                or result.get("thread_id")
                or result.get("chat_id")
            )

            # Include conversation_id if found, or echo back input conversation_id
            if response_conversation_id:
                response_payload["conversation_id"] = response_conversation_id
            elif conversation_id:
                response_payload["conversation_id"] = conversation_id

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
                f"trace_id={trace_id}, conversation_id={response_payload.get('conversation_id')}"
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

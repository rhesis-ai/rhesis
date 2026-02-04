"""WebSocket endpoint for real-time frontend communication.

This module provides the main WebSocket endpoint for frontend connections,
supporting authentication, channel subscriptions, and message handling.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ValidationError

from rhesis.backend.app.auth.user_utils import (
    get_authenticated_user_with_context,
    get_secret_key,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.websocket import EventType, WebSocketMessage
from rhesis.backend.app.services.websocket import get_ws_token_service, ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Security: Maximum message size (64KB) to prevent DoS attacks
MAX_MESSAGE_SIZE = 65536


class WebSocketTokenResponse(BaseModel):
    """Response model for WebSocket token endpoint."""

    token: str
    expires_in: int  # Seconds until expiration


@router.post("/ws/token", response_model=WebSocketTokenResponse)
async def get_websocket_token(
    current_user: User = Depends(get_authenticated_user_with_context),
) -> WebSocketTokenResponse:
    """Get a short-lived token for WebSocket connection.

    This endpoint issues a single-use token with a 60-second TTL.
    The token should be used immediately to establish a WebSocket connection.

    Returns:
        WebSocketTokenResponse with the token and expiration time.
    """
    token_service = get_ws_token_service()
    token = token_service.create_ws_token(
        user_id=str(current_user.id),
        org_id=str(current_user.organization_id),
    )
    return WebSocketTokenResponse(
        token=token,
        expires_in=token_service.WS_TOKEN_TTL_SECONDS,
    )


async def authenticate_websocket_token(
    websocket: WebSocket,
    token: Optional[str] = None,
) -> Optional[User]:
    """Authenticate WebSocket connection using token from query parameter.

    This function supports two authentication methods:
    1. Short-lived WebSocket tokens (preferred, more secure)
    2. Regular JWT tokens (fallback for compatibility)

    Args:
        websocket: The WebSocket connection.
        token: JWT, WebSocket token, or API token from query parameter.

    Returns:
        Authenticated User object, or None if authentication fails.
    """
    if not token:
        return None

    # First, try WebSocket-specific token (short-lived, single-use)
    ws_token_service = get_ws_token_service()
    ws_payload = ws_token_service.validate_ws_token(token)
    if ws_payload:
        # WebSocket token is valid - look up user
        from rhesis.backend.app.crud import get_db
        from rhesis.backend.app.models.user import User as UserModel

        try:
            db = next(get_db())
            user = db.query(UserModel).filter(UserModel.id == ws_payload["sub"]).first()
            if user:
                logger.debug(f"WebSocket auth via WS token for user {user.id}")
                return user
        except Exception as e:
            logger.warning(f"WebSocket token user lookup failed: {e}")
        finally:
            db.close()

    # Fall back to regular JWT/API token authentication
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    # Create minimal mock request (websockets don't have full Request object)
    class MockRequest:
        def __init__(self):
            self.session = {}
            self.state = type("obj", (object,), {})()

    mock_request = MockRequest()

    try:
        # Use existing authentication logic (supports both rh- tokens and JWT)
        user = await get_authenticated_user_with_context(
            request=mock_request,
            credentials=credentials,
            secret_key=get_secret_key(),
            without_context=False,  # Require organization
        )
        return user
    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for frontend connections.

    Authentication is performed via query parameter: /ws?token=<jwt>

    This endpoint handles:
    - Connection authentication
    - Channel subscriptions (via SUBSCRIBE/UNSUBSCRIBE messages)
    - Message routing to appropriate handlers
    - Connection lifecycle management

    Message Format:
        {
            "type": "subscribe" | "unsubscribe" | "ping" | ...,
            "channel": "optional_channel_name",
            "payload": { ... optional data ... },
            "correlation_id": "optional_correlation_id"
        }
    """
    # Get token from query parameter
    token = websocket.query_params.get("token")

    # Authenticate
    user = await authenticate_websocket_token(websocket, token)
    if not user:
        logger.warning("WebSocket authentication failed - closing connection")
        await websocket.close(code=1008, reason="Authentication failed")
        return

    # Accept the connection
    await websocket.accept()

    # Register with manager
    conn_id = await ws_manager.connect(websocket, user)

    # Send connected confirmation
    try:
        await websocket.send_json(
            {
                "type": EventType.CONNECTED.value,
                "payload": {
                    "connection_id": conn_id,
                    "user_id": str(user.id),
                    "org_id": str(user.organization_id),
                },
            }
        )
    except Exception as e:
        logger.error(f"Failed to send connected message: {e}")
        ws_manager.disconnect(conn_id)
        return

    # Main message loop
    try:
        while True:
            # Receive raw message to check size before parsing
            raw_data = await websocket.receive_text()

            # Security: Check message size before parsing
            if len(raw_data) > MAX_MESSAGE_SIZE:
                logger.warning(f"Message too large from {conn_id}: {len(raw_data)} bytes")
                try:
                    await websocket.send_json(
                        {
                            "type": EventType.ERROR.value,
                            "payload": {"error": "Message exceeds maximum size (64KB)"},
                        }
                    )
                except Exception:
                    pass
                continue

            try:
                # Parse JSON
                data = json.loads(raw_data)

                # Validate message
                message = WebSocketMessage(**data)

                # Route to handler
                await ws_manager.handle_message(conn_id, user, message)

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from {conn_id}")
                try:
                    await websocket.send_json(
                        {
                            "type": EventType.ERROR.value,
                            "payload": {"error": "Invalid message format"},
                        }
                    )
                except Exception:
                    pass
            except ValidationError as e:
                # Security: Log full details server-side, return generic message to client
                logger.warning(f"Validation error from {conn_id}: {e}")
                try:
                    await websocket.send_json(
                        {
                            "type": EventType.ERROR.value,
                            "payload": {"error": "Invalid message format"},
                        }
                    )
                except Exception:
                    pass
            except Exception as e:
                # Security: Log full details server-side, return generic message to client
                # Never expose internal exception details to clients
                logger.error(
                    f"Error handling WebSocket message from {conn_id}: {e}",
                    exc_info=True,
                )
                try:
                    await websocket.send_json(
                        {
                            "type": EventType.ERROR.value,
                            "payload": {"error": "Internal server error"},
                        }
                    )
                except Exception:
                    pass  # Connection might be closed

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {conn_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {conn_id}: {e}")
    finally:
        # Clean up connection
        ws_manager.disconnect(conn_id)

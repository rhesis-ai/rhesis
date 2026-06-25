"""WebSocket endpoint for real-time frontend communication.

This module provides the main WebSocket endpoint for frontend connections,
supporting authentication, channel subscriptions, and message handling.
"""

import json
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ValidationError

from rhesis.backend.app.auth.principal import (
    REQUEST_STATE_AUTH_KIND,
    AuthKind,
    Principal,
    resolve_principal,
    resolve_principal_from_request,
)
from rhesis.backend.app.auth.user_utils import (
    get_authenticated_user_with_context,
    get_secret_key,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.websocket import EventType, WebSocketMessage
from rhesis.backend.app.services.websocket import get_ws_token_service, ws_manager

logger = logging.getLogger(__name__)

router = RhesisRouter(tags=["websocket"], resource="websocket")

# Security: Maximum message size (10MB) to accommodate base64-encoded file attachments
MAX_MESSAGE_SIZE = 10 * 1024 * 1024


class WebSocketTokenResponse(BaseModel):
    """Response model for WebSocket token endpoint."""

    token: str
    expires_in: int  # Seconds until expiration


@router.post("/ws/token", response_model=WebSocketTokenResponse)
async def get_websocket_token(
    request: Request,
    current_user: User = Depends(get_authenticated_user_with_context),
) -> WebSocketTokenResponse:
    """Get a short-lived token for WebSocket connection.

    This endpoint issues a single-use token with a 60-second TTL.
    The token should be used immediately to establish a WebSocket connection.

    Returns:
        WebSocketTokenResponse with the token and expiration time.
    """
    # Security (SP9): a WS token carries no scopes, so it always resolves to a
    # full-access session principal on connect. Allowing an API token to mint one
    # would let a *scoped* rh-* token escalate to full session access over the WS
    # transport. WS tokens are therefore session-only; API-token clients connect
    # to /ws directly with their token (the bearer path preserves their scopes).
    # NOTE: get_authenticated_user_with_context only flags rh-* tokens as
    # AuthKind.TOKEN; widen this guard if M2M JWTs ever carry SP9 scopes.
    if getattr(request.state, REQUEST_STATE_AUTH_KIND, AuthKind.SESSION) == AuthKind.TOKEN:
        raise HTTPException(
            status_code=403,
            detail=(
                "WebSocket tokens must be minted from a session; "
                "connect to /ws directly with your API token instead"
            ),
        )
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
) -> Optional[tuple[User, "Principal"]]:
    """Authenticate WebSocket connection using token from query parameter.

    This function supports two authentication methods:
    1. Short-lived WebSocket tokens (preferred, more secure)
    2. Regular JWT/rh-* tokens (fallback for compatibility)

    Returns a (User, Principal) pair so token scopes are preserved for
    channel authorization (SP9).  Returns None if authentication fails.
    """
    if not token:
        return None

    # First, try WebSocket-specific token (short-lived, single-use)
    ws_token_service = get_ws_token_service()
    ws_payload = ws_token_service.validate_ws_token(token)
    if ws_payload:
        # WebSocket token is valid - look up user
        from rhesis.backend.app.database import get_db
        from rhesis.backend.app.models.user import User as UserModel

        try:
            with get_db() as db:
                user = db.query(UserModel).filter(UserModel.id == ws_payload["sub"]).first()
                if user:
                    logger.debug(f"WebSocket auth via WS token for user {user.id}")
                    # WS tokens are always issued from session auth — session principal.
                    return user, resolve_principal(user)
        except Exception as e:
            logger.warning(f"WebSocket token user lookup failed: {e}")

    # Fall back to regular JWT/API token authentication
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    # Create minimal mock request (websockets don't have full Request object)
    class MockRequest:
        def __init__(self):
            self.session = {}
            self.state = type("obj", (object,), {})()

    mock_request = MockRequest()

    try:
        # Use existing authentication logic (supports both rh- tokens and JWT).
        # get_authenticated_user_with_context writes token context to mock_request.state
        # so resolve_principal_from_request can harvest it below.
        user = await get_authenticated_user_with_context(
            request=mock_request,
            credentials=credentials,
            secret_key=get_secret_key(),
            without_context=False,  # Require organization
        )
        if user:
            return user, resolve_principal_from_request(user, mock_request)
        return None
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
    auth = await authenticate_websocket_token(websocket, token)
    if not auth:
        logger.warning("WebSocket authentication failed - closing connection")
        await websocket.close(code=1008, reason="Authentication failed")
        return
    user, principal = auth

    # Accept the connection
    await websocket.accept()

    # Register with manager; store the principal so channel authorization
    # can apply SP9 token scope intersection.
    conn_id = await ws_manager.connect(websocket, user)
    ws_manager.register_principal(conn_id, principal)

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
                            "payload": {"error": "Message exceeds maximum size (10MB)"},
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

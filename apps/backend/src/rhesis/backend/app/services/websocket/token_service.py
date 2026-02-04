"""WebSocket-specific token service.

This module provides short-lived tokens for WebSocket connections,
mitigating the security risk of passing tokens in URL query parameters.

Security benefits:
- Tokens expire quickly (60 seconds by default)
- Tokens are purpose-specific (cannot be reused for other APIs)
- Reduces exposure window if token is logged or intercepted
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from rhesis.backend.app.auth.user_utils import get_secret_key

logger = logging.getLogger(__name__)


class WebSocketTokenService:
    """Issues and validates short-lived tokens for WebSocket connections.

    These tokens:
    - Have a short TTL (default 60 seconds)
    - Are purpose-specific (purpose="websocket")
    - Include a unique JTI to prevent reuse
    - Are single-use (tracked to prevent replay)

    Example usage:
        service = get_ws_token_service()

        # Issue token (after authenticating user via API)
        token = service.create_ws_token(user_id="...", org_id="...")

        # Validate token (during WebSocket connection)
        payload = service.validate_ws_token(token)
        if payload:
            # Token is valid, proceed with connection
    """

    WS_TOKEN_TTL_SECONDS = 60  # 1 minute
    ALGORITHM = "HS256"
    PURPOSE = "websocket"

    def __init__(self, secret_key: Optional[str] = None):
        """Initialize the token service.

        Args:
            secret_key: Secret key for signing tokens.
                       If not provided, uses the application secret key.
        """
        self._secret_key = secret_key or get_secret_key()
        # Track used tokens to prevent replay (in-memory, resets on restart)
        # For production, this should be Redis-backed for multi-instance support
        self._used_tokens: set[str] = set()

    def create_ws_token(self, user_id: str, org_id: str) -> str:
        """Create a short-lived token for WebSocket connection.

        Args:
            user_id: The user's ID.
            org_id: The user's organization ID.

        Returns:
            A signed JWT token for WebSocket authentication.
        """
        now = datetime.now(timezone.utc)
        jti = secrets.token_hex(16)  # Unique token ID

        payload = {
            "sub": user_id,
            "org": org_id,
            "purpose": self.PURPOSE,
            "jti": jti,
            "exp": now + timedelta(seconds=self.WS_TOKEN_TTL_SECONDS),
            "iat": now,
        }

        token = jwt.encode(payload, self._secret_key, algorithm=self.ALGORITHM)
        logger.debug(f"Created WebSocket token for user {user_id}")
        return token

    def validate_ws_token(self, token: str) -> Optional[dict]:
        """Validate a WebSocket-specific token.

        Checks:
        - Token signature is valid
        - Token is not expired
        - Token has correct purpose
        - Token has not been used before (single-use)

        Args:
            token: The JWT token to validate.

        Returns:
            The token payload if valid, None otherwise.
        """
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self.ALGORITHM],
            )

            # Verify purpose
            if payload.get("purpose") != self.PURPOSE:
                logger.warning("WebSocket token has wrong purpose")
                return None

            # Verify JTI exists
            jti = payload.get("jti")
            if not jti:
                logger.warning("WebSocket token missing JTI")
                return None

            # Check if token was already used (prevent replay)
            if jti in self._used_tokens:
                logger.warning(f"WebSocket token already used: {jti[:8]}...")
                return None

            # Mark token as used
            self._used_tokens.add(jti)

            # Clean up old tokens periodically (simple cleanup)
            if len(self._used_tokens) > 10000:
                self._cleanup_used_tokens()

            logger.debug(f"Validated WebSocket token for user {payload.get('sub')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("WebSocket token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid WebSocket token: {e}")
            return None

    def _cleanup_used_tokens(self) -> None:
        """Clean up old used tokens.

        Note: This is a simple cleanup. In production with Redis,
        you would use TTL-based expiration instead.
        """
        # Keep only the most recent 5000 tokens
        if len(self._used_tokens) > 5000:
            # Convert to list, keep last 5000, convert back to set
            # This is imprecise but prevents unbounded memory growth
            self._used_tokens = set(list(self._used_tokens)[-5000:])
            logger.info("Cleaned up used WebSocket tokens")

    def invalidate_token(self, jti: str) -> None:
        """Manually invalidate a token by its JTI.

        Args:
            jti: The unique token ID to invalidate.
        """
        self._used_tokens.add(jti)


# Singleton instance
_token_service: Optional[WebSocketTokenService] = None


def get_ws_token_service() -> WebSocketTokenService:
    """Get or create the WebSocket token service singleton."""
    global _token_service
    if _token_service is None:
        _token_service = WebSocketTokenService()
    return _token_service

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.token import get_token_by_value

logger = logging.getLogger(__name__)

#: Minimum gap between two ``last_used_at`` writes for one token. Without it every
#: API-token request is an UPDATE inside the auth transaction; "last used within
#: the last five minutes" is all the field is read for.
TOKEN_USAGE_WRITE_INTERVAL = timedelta(minutes=5)


def update_token_usage(db: Session, token) -> None:
    """Stamp ``last_used_at``, at most once per :data:`TOKEN_USAGE_WRITE_INTERVAL`."""
    try:
        now = datetime.now(timezone.utc)
        last_used = token.last_used_at
        if last_used is not None:
            if last_used.tzinfo is None:
                last_used = last_used.replace(tzinfo=timezone.utc)
            if now - last_used < TOKEN_USAGE_WRITE_INTERVAL:
                return
        token.last_used_at = now
        db.add(token)
        # Transaction commit/rollback is handled by the session context manager
    except Exception as e:
        logger.error(f"Failed to update token last_used_at: {str(e)}")
        # Transaction rollback is handled by the session context manager


def validate_token(
    token_or_value, update_usage: bool = True, db: Session = None
) -> tuple[bool, Optional[str]]:
    """
    Validate token format, existence, and expiration. Optionally update usage.
    Returns (is_valid, error_message)
    """
    # Handle both token value strings and token objects
    if isinstance(token_or_value, str):
        if not token_or_value.startswith("rh-"):
            return False, "Invalid token format. Token must start with 'rh-'"
        if not db:
            return False, "Database session required to validate token value"
        token = get_token_by_value(db, token_or_value)
    else:
        token = token_or_value

    if not token:
        return False, "Invalid or revoked token"

    # Check expiration only if expires_at is not None
    if token.expires_at:
        # Make sure token.expires_at is timezone-aware
        token_expiry = (
            token.expires_at
            if token.expires_at.tzinfo
            else token.expires_at.replace(tzinfo=timezone.utc)
        )
        now = datetime.now(timezone.utc)

        if token_expiry <= now:
            return False, "Token has expired"

    if update_usage and db:
        update_token_usage(db, token)

    return True, None

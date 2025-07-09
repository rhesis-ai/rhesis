from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.logging import logger

def update_token_usage(db: Session, token) -> None:
    """Update the last_used_at timestamp for a token."""
    try:
        token.last_used_at = datetime.now(timezone.utc)
        db.add(token)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to update token last_used_at: {str(e)}")
        db.rollback()

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
        token = crud.get_token_by_value(db, token_or_value)
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
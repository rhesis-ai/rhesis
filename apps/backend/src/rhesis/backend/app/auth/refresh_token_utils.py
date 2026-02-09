"""Refresh token creation, verification, rotation, and revocation.

Refresh tokens are opaque random strings.  Only the SHA-256 hash is
stored in the database (``RefreshToken`` model).  Tokens belong to a
``family`` — a rotation chain starting from a login event.  If a
previously-revoked token is presented (reuse detection), every token
in the family is revoked to protect against token theft.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.constants import REFRESH_TOKEN_EXPIRE_DAYS
from rhesis.backend.app.models.refresh_token import RefreshToken
from rhesis.backend.logging import logger


def _hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of *raw_token*."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_refresh_token(
    db: Session,
    user_id: str,
    family_id: str | None = None,
) -> str:
    """Create and persist a new refresh token, returning the raw value.

    Parameters
    ----------
    db:
        Active database session.
    user_id:
        ID of the user the token belongs to.
    family_id:
        Optional family ID for token rotation.  When ``None`` a new
        family is started (initial login).

    Returns
    -------
    str
        The raw opaque token.  This is the *only* time the raw value
        is available — only the hash is stored.
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    if family_id is None:
        family_id = str(uuid.uuid4())

    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        family_id=family_id,
        expires_at=expires_at,
    )
    db.add(db_token)
    db.flush()  # assign id without committing

    logger.info(
        "Refresh token created for user %s (family %s)",
        user_id,
        family_id,
    )
    return raw_token


def verify_and_rotate_refresh_token(
    db: Session,
    raw_token: str,
) -> tuple[RefreshToken, str]:
    """Verify a refresh token and rotate it.

    If the token is valid, it is revoked and a new token from the same
    family is created (rotation).

    If the token was already revoked (potential theft), all tokens in
    the family are revoked and an ``HTTPException(401)`` is raised.

    Returns
    -------
    tuple[RefreshToken, str]
        The old ``RefreshToken`` row (now revoked) and the new raw
        opaque token.
    """
    token_hash = _hash_token(raw_token)

    db_token: RefreshToken | None = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    )

    if db_token is None:
        logger.warning("Refresh token not found (hash %s…)", token_hash[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # ------------------------------------------------------------------
    # Reuse detection: if the token was already revoked, someone may
    # have stolen the old token.  Revoke the entire family.
    # ------------------------------------------------------------------
    if db_token.is_revoked:
        logger.warning(
            "Reuse detected for family %s — revoking entire family",
            db_token.family_id,
        )
        _revoke_family(db, db_token.family_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected — session revoked",
        )

    if db_token.is_expired:
        logger.info("Expired refresh token for user %s", db_token.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Revoke the current token (rotation)
    db_token.revoked_at = datetime.now(timezone.utc)

    # Issue a new token in the same family
    new_raw_token = create_refresh_token(
        db,
        user_id=str(db_token.user_id),
        family_id=str(db_token.family_id),
    )

    return db_token, new_raw_token


def revoke_all_for_user(db: Session, user_id: str) -> int:
    """Revoke every refresh token belonging to *user_id*.

    Returns the number of tokens revoked.
    """
    now = datetime.now(timezone.utc)
    count = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .update({"revoked_at": now})
    )
    logger.info("Revoked %d refresh tokens for user %s", count, user_id)
    return count


def _revoke_family(db: Session, family_id: str) -> int:
    """Revoke every token in a rotation family."""
    now = datetime.now(timezone.utc)
    count = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .update({"revoked_at": now})
    )
    logger.info("Revoked %d tokens in family %s", count, family_id)
    return count


def cleanup_expired_tokens(db: Session) -> int:
    """Delete refresh tokens that are expired *and* revoked.

    Intended to be called periodically (e.g. Celery beat) to keep the
    table from growing indefinitely.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    count = db.query(RefreshToken).filter(RefreshToken.expires_at < cutoff).delete()
    logger.info("Cleaned up %d expired refresh tokens", count)
    return count

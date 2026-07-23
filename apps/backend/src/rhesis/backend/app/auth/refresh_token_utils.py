"""Refresh token creation, verification, rotation, and revocation.

Refresh tokens are opaque random strings.  Only the SHA-256 hash is
stored in the database (``RefreshToken`` model).  Tokens belong to a
``family`` — a rotation chain starting from a login event.  If a
previously-revoked token is presented (reuse detection), every token
in the family is revoked to protect against token theft.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.constants import (
    AUTH_ABSOLUTE_SESSION_MAX_DAYS,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from rhesis.backend.app.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)


def _hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of *raw_token*."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_refresh_token(
    db: Session,
    user_id: str,
    family_id: str | None = None,
    *,
    client_id: str | None = None,
    scope: str | None = None,
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
    client_id:
        Optional :class:`AuthClient` ``client_id`` when the token is
        being minted via ``/auth/token-exchange``. NULL for UI/SSO
        refresh tokens. When set, ``/auth/refresh`` requires HTTP
        Basic credentials matching this client (S2/S3).
    scope:
        Optional space-separated scope string. Set alongside
        ``client_id`` so the new access token minted on rotation
        preserves the original scope (without this, a ``scope=read``
        token-exchange refresh would silently escalate to full-user
        on its first refresh).

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
        client_id=client_id,
        scope=scope,
    )
    db.add(db_token)
    db.flush()  # assign id without committing

    logger.info(
        "Refresh token created for user %s (family %s, client_id=%s)",
        user_id,
        family_id,
        client_id or "none",
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

    # Issue a new token in the same family, propagating client_id and
    # scope so that token-exchange-minted refresh chains keep their
    # binding across rotation. UI/SSO tokens have both NULL and the
    # propagation is a no-op.
    new_raw_token = create_refresh_token(
        db,
        user_id=str(db_token.user_id),
        family_id=str(db_token.family_id),
        client_id=db_token.client_id,
        scope=db_token.scope,
    )

    return db_token, new_raw_token


def verify_and_refresh_token(
    db: Session,
    raw_token: str,
) -> tuple[RefreshToken, str]:
    """Validate a refresh token and return ``(row, refresh_token_to_return)``.

    The rotation policy depends on the token's client binding:

    * **UI / SSO tokens** (``client_id IS NULL``) are **not rotated**.
      The same opaque token is returned and its expiry is pushed out
      (sliding window). Browser sessions are managed by NextAuth, whose
      ``jwt`` callback frequently runs inside Next.js React Server
      Component renders that cannot write a rotated cookie back to the
      browser. Rotating there would revoke the presented token while the
      client kept using it, tripping reuse detection and forcing a
      logout on the very next request. Keeping the token stable makes
      refresh idempotent and race-free. The token is still revoked on
      logout (:func:`revoke_all_for_user`), honours the ``is_active``
      kill switch at the endpoint, and hard-expires
      ``REFRESH_TOKEN_EXPIRE_DAYS`` after its last use.

    * **Token-exchange tokens** (``client_id IS NOT NULL``) keep per-use
      rotation with reuse detection unchanged — the confidential client
      persists the rotated token itself, so the NextAuth limitation does
      not apply. This path delegates to
      :func:`verify_and_rotate_refresh_token`.

    Returns
    -------
    tuple[RefreshToken, str]
        The token row and the raw refresh token the caller should return
        to the client: the successor for token-exchange tokens, the same
        (unchanged) token for UI/SSO tokens.
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

    # Token-exchange tokens keep the rotating behaviour (and reuse
    # detection) exactly as before.
    if db_token.client_id is not None:
        return verify_and_rotate_refresh_token(db, raw_token)

    # ------------------------------------------------------------------
    # UI / SSO stable-token path
    # ------------------------------------------------------------------
    if db_token.is_revoked:
        # A revoked UI/SSO token means the session was ended (logout,
        # user disabled, family revocation). There is no rotated "old"
        # token to distinguish from theft here, so reject plainly rather
        # than nuking the family.
        logger.info("Revoked UI/SSO refresh token presented for user %s", db_token.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if db_token.is_expired:
        logger.info("Expired refresh token for user %s", db_token.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    now = datetime.now(timezone.utc)

    # Absolute session cap: even an actively-refreshed session must
    # re-authenticate once its family is AUTH_ABSOLUTE_SESSION_MAX_DAYS old.
    # The family's age is the earliest created_at across the family (the
    # login event). Reject once the cap is passed; otherwise slide the
    # inactivity window but never past the absolute deadline.
    family_started_at = (
        db.query(func.min(RefreshToken.created_at))
        .filter(RefreshToken.family_id == db_token.family_id)
        .scalar()
    )
    if family_started_at is not None:
        if family_started_at.tzinfo is None:
            family_started_at = family_started_at.replace(tzinfo=timezone.utc)
        absolute_deadline = family_started_at + timedelta(days=AUTH_ABSOLUTE_SESSION_MAX_DAYS)
        if absolute_deadline <= now:
            logger.info(
                "Refresh rejected: session for user %s exceeded absolute cap "
                "(family %s started %s)",
                db_token.user_id,
                db_token.family_id,
                family_started_at,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
            )
    else:
        absolute_deadline = None

    # Slide the expiry forward so active sessions persist, matching the
    # previous rotating behaviour where each refresh reset the window --
    # but never beyond the absolute deadline.
    sliding_expiry = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db_token.expires_at = (
        min(sliding_expiry, absolute_deadline) if absolute_deadline is not None else sliding_expiry
    )

    return db_token, raw_token


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

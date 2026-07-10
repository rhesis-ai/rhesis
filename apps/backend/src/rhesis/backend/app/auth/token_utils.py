import base64
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import jwt
from fastapi import HTTPException, status
from jwt import PyJWTError as JWTError

from rhesis.backend.app.config.settings import get_auth_settings
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.redact import redact_email

logger = logging.getLogger(__name__)

# Token expiry defaults (in minutes)
SERVICE_DELEGATION_EXPIRE_MINUTES = int(os.getenv("SERVICE_DELEGATION_EXPIRE_MINUTES", "15"))
EMAIL_VERIFICATION_EXPIRE_MINUTES = 60 * 24  # 24 hours
PASSWORD_RESET_EXPIRE_MINUTES = 60  # 1 hour
MAGIC_LINK_EXPIRE_MINUTES = 15  # 15 minutes
AUTH_CODE_EXPIRE_MINUTES = 1  # 60 seconds, for OAuth callback redirect

#: Audience claim stamped on token-exchange-issued JWTs and enforced by
#: :func:`verify_jwt_token` whenever ``azp`` is present. Configurable via
#: env so a deployment with multiple Rhesis backends behind a router can
#: distinguish them. UI/SSO tokens omit ``aud`` entirely and skip the check.
RHESIS_TOKEN_AUDIENCE = os.getenv("RHESIS_TOKEN_AUDIENCE", "rhesis-api")


def get_secret_key() -> str:
    """Get JWT secret key from application settings."""
    secret_key = get_auth_settings().jwt_secret_key
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET_KEY not configured",
        )
    return secret_key


def get_jwt_algorithm() -> str:
    """Get JWT signing algorithm from application settings."""
    return get_auth_settings().jwt_algorithm


def get_access_token_expire_minutes() -> int:
    """Get session access token lifetime from application settings."""
    return get_auth_settings().jwt_access_token_expire_minutes


def create_session_token(
    user: User,
    *,
    azp: Optional[str] = None,
    aud: Optional[str] = None,
    scope: Optional[str] = None,
    jti: Optional[str] = None,
    epoch: Optional[Union[datetime, int]] = None,
) -> str:
    """Create a new session token for a user.

    Default behaviour (every existing UI / SSO call site, no extra
    keyword args) is byte-identical to the pre-extension version: the
    payload contains ``sub``, ``iat``, ``exp``, ``type``, and ``user``
    only. The snapshot test in
    ``tests/backend/auth/test_session_utils.py`` enforces this so a
    later edit cannot quietly add a default claim and break clients
    that pin on the payload shape.

    When any of the keyword args is set the token is a
    **token-exchange-issued** JWT. The token ``type`` stays
    ``"session"`` so the existing :func:`verify_jwt_token` allowlist
    still accepts it; the new claims layer on top:

    - ``azp`` -- authorized party, the calling client's identifier
      (e.g. ``"brain"``). Triggers the audience and epoch checks in
      :func:`verify_jwt_token`.
    - ``aud`` -- defaults to :data:`RHESIS_TOKEN_AUDIENCE` when ``azp``
      is set; ignored otherwise. Setting ``aud`` without ``azp`` is a
      programmer error and raises immediately so a misconfigured caller
      cannot mint an unverifiable token.
    - ``scope`` -- space-separated scope string for forward-compatible
      per-route enforcement.
    - ``jti`` -- per-token UUID, logged in the issuance audit event so
      a leaked token can be correlated to its origin during forensics.
    - ``epoch`` -- ``AuthClient.token_epoch`` as either a UTC datetime
      or unix seconds. **Required** whenever ``azp`` is set: it is
      stored as integer seconds in the JWT so the ``iat >= epoch``
      check at verify time is one int comparison with no DB lookup,
      and that is the entire mechanism behind coarse revocation.
      Minting an azp-bearing token without it raises immediately.
    """
    if aud is not None and azp is None:
        # An ``aud`` without ``azp`` is unverifiable: ``verify_jwt_token``
        # only enforces ``aud`` when ``azp`` is present, so the audience
        # claim would be silently ignored. Fail at mint time so the
        # programmer error surfaces immediately rather than as a token
        # that "looks bound" but isn't.
        raise ValueError("aud cannot be set without azp")
    if azp is not None and epoch is None:
        # Symmetric guard: ``epoch`` is the *only* mechanism behind
        # coarse revocation, and ``verify_jwt_token`` rejects azp-bearing
        # tokens that lack it. Minting without ``epoch`` would produce
        # a token that fails verification immediately -- catch the
        # programmer error here instead of at the first request.
        raise ValueError("epoch is required whenever azp is set")

    expires_delta = timedelta(minutes=get_access_token_expire_minutes())
    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    # Convert UUID to string for JSON serialization
    organization_id = str(user.organization_id) if user.organization_id else None

    to_encode: Dict[str, Any] = {
        "sub": str(user.id),
        "iat": now,
        "exp": expire,
        "type": "session",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "is_email_verified": getattr(user, "is_email_verified", True),
            "organization_id": organization_id,
        },
    }

    if azp is not None:
        to_encode["azp"] = azp
        to_encode["aud"] = aud if aud is not None else RHESIS_TOKEN_AUDIENCE
        if scope is not None:
            to_encode["scope"] = scope
        # ``jti`` falls back to a fresh uuid4 because the audit trail
        # depends on it being unique per issuance; without that we
        # cannot trace a leaked token to its source.
        to_encode["jti"] = jti if jti is not None else str(uuid.uuid4())
        if epoch is not None:
            if isinstance(epoch, datetime):
                if epoch.tzinfo is None:
                    epoch = epoch.replace(tzinfo=timezone.utc)
                to_encode["epoch"] = int(epoch.timestamp())
            else:
                to_encode["epoch"] = int(epoch)
    elif scope is not None or jti is not None or epoch is not None:
        # Same reasoning as the aud-without-azp guard: the new claims
        # only have meaning in concert with ``azp``. Smuggling them in
        # alone would produce a token that looks bound but isn't.
        raise ValueError("scope/jti/epoch require azp to be set")

    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=get_jwt_algorithm())
    return encoded_jwt


def create_service_delegation_token(
    user: User,
    target_service: str,
    expires_minutes: int = SERVICE_DELEGATION_EXPIRE_MINUTES,
) -> str:
    """Create a short-lived delegation token for service-to-service calls on behalf of a user."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)

    organization_id = str(user.organization_id) if user.organization_id else None

    to_encode = {
        "sub": str(user.id),
        "iat": now,
        "nbf": now,
        "exp": expire,
        "type": "service_delegation",
        "target_service": target_service,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "organization_id": organization_id,
        },
    }

    return jwt.encode(to_encode, get_secret_key(), algorithm=get_jwt_algorithm())


def verify_jwt_token(token: str, secret_key: str, algorithm: str | None = None) -> Dict[str, Any]:
    """Verify and decode a Rhesis-minted JWT.

    Returns the decoded payload on success; raises :class:`JWTError`
    (or :class:`jwt.ExpiredSignatureError` specifically for expiry) on
    every failure mode.

    The ``algorithms=[algorithm]`` allowlist is explicit and pinned to
    the configured JWT algorithm. Letting PyJWT derive the algorithm from
    the token header would re-introduce the canonical "alg=none" /
    HS-vs-RS confusion class; the allowlist guarantees we only accept
    HS256-signed tokens with our own secret. This is regression-tested
    in ``tests/backend/auth/`` -- do not collapse it back to ``None``.

    Token-exchange-issued JWTs (anything carrying an ``azp`` claim)
    pick up three additional checks beyond the standard exp/iat:

    - ``aud`` MUST be present and equal to :data:`RHESIS_TOKEN_AUDIENCE`.
      Without this check, a token issued for some other Rhesis backend
      (different ``RHESIS_TOKEN_AUDIENCE``) would be accepted here.
    - ``epoch`` MUST be present. The whole client-bound revocation
      model rests on the ``iat >= epoch`` comparison; a token minted
      with ``azp`` but no ``epoch`` (programmer error or tampering)
      would silently bypass coarse revocation and survive a secret
      rotation. Reject loudly rather than fail-open.
    - ``iat >= epoch`` MUST hold. ``epoch`` is the unix-seconds copy
      of ``AuthClient.token_epoch`` embedded at mint time; bumping
      ``token_epoch`` invalidates every previously issued token via
      this check, with no DB lookup at verify time. That is the
      entire mechanism behind coarse client-level revocation in v1.

    UI / SSO tokens carry no ``azp`` and skip all three checks, which
    keeps their payload byte-identical to the pre-extension shape.
    """
    algorithm = algorithm or get_jwt_algorithm()
    try:
        # PyJWT's built-in ``verify_aud`` requires us to pass the
        # expected audience; we verify it manually below only when
        # ``azp`` is present, so we disable PyJWT's own ``aud`` check
        # for the call. The decode still verifies signature, exp, and
        # iat, which is the bulk of the protection.
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": False,
                "require": ["exp", "iat"],
            },
        )

        # Check token type — allow session and service delegation tokens
        allowed_types = {"session", "service_delegation"}
        if payload.get("type") not in allowed_types:
            logger.warning(f"Invalid token type: {payload.get('type')}")
            raise JWTError("Invalid token type")

        if "azp" in payload:
            aud = payload.get("aud")
            if aud != RHESIS_TOKEN_AUDIENCE:
                # Same JWTError shape as a tampered signature so the
                # caller has no oracle distinguishing "bad audience"
                # from "bad signature".
                logger.warning(
                    "JWT azp present but aud mismatch (azp=%s)",
                    payload.get("azp"),
                )
                raise JWTError("Invalid audience")

            # ``epoch`` is required whenever ``azp`` is set: it is the
            # only knob behind coarse client-level revocation. Treating
            # a missing ``epoch`` as "skip the check" would mean a token
            # minted by a buggy or compromised path could survive
            # rotation forever; we'd rather reject the token than
            # silently grant it immortality.
            epoch = payload.get("epoch")
            iat = payload.get("iat")
            if epoch is None:
                logger.warning(
                    "JWT azp=%s present but epoch missing; rejecting",
                    payload.get("azp"),
                )
                raise JWTError("Token revoked")
            if iat is not None and int(iat) < int(epoch):
                logger.warning(
                    "JWT iat (%s) < client token_epoch (%s); coarse revocation",
                    iat,
                    epoch,
                )
                raise JWTError("Token revoked")

        if "user" in payload:
            logger.debug(
                "JWT token validated for user: %s",
                redact_email(payload["user"].get("email") or ""),
            )
            logger.debug(
                f"Token expiration: {datetime.fromtimestamp(payload['exp'], tz=timezone.utc)}"
            )

        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise
    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        raise


# =========================================================================
# Email flow tokens (verification, password reset, magic link)
# =========================================================================


def _create_email_flow_token(
    user_id: str,
    email: str,
    token_type: str,
    expire_minutes: int,
    extra_claims: Optional[Dict[str, Any]] = None,
    *,
    with_jti: bool = False,
) -> str:
    """
    Create a short-lived JWT for email-based flows.

    Args:
        user_id: The user's ID (as string).
        email: The user's email address.
        token_type: One of 'email_verification', 'password_reset',
                    or 'magic_link'.
        expire_minutes: Token lifetime in minutes.
        extra_claims: Optional additional claims.
        with_jti: If True, add a unique jti claim for single-use tracking.

    Returns:
        Signed JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    if with_jti:
        payload["jti"] = str(uuid.uuid4())
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, get_secret_key(), algorithm=get_jwt_algorithm())


def create_email_verification_token(user_id: str, email: str) -> str:
    """Create a 24-hour email verification token."""
    return _create_email_flow_token(
        user_id=user_id,
        email=email,
        token_type="email_verification",
        expire_minutes=EMAIL_VERIFICATION_EXPIRE_MINUTES,
    )


def create_password_reset_token(user_id: str, email: str) -> str:
    """Create a 1-hour single-use password reset token."""
    return _create_email_flow_token(
        user_id=user_id,
        email=email,
        token_type="password_reset",
        expire_minutes=PASSWORD_RESET_EXPIRE_MINUTES,
        with_jti=True,
    )


def create_magic_link_token(
    user_id: str,
    email: str,
    *,
    terms_accepted: bool = False,
) -> str:
    """Create a 15-minute single-use magic link login token."""
    extra_claims = {"terms_accepted": True} if terms_accepted else None
    return _create_email_flow_token(
        user_id=user_id,
        email=email,
        token_type="magic_link",
        expire_minutes=MAGIC_LINK_EXPIRE_MINUTES,
        extra_claims=extra_claims,
        with_jti=True,
    )


def verify_email_flow_token(token: str, expected_type: str) -> Dict[str, Any]:
    """
    Verify a token from an email flow (verification, reset, magic link).

    Args:
        token: The JWT token string.
        expected_type: The expected ``type`` claim.

    Returns:
        Decoded payload dict with ``sub``, ``email``, ``type``.

    Raises:
        HTTPException: If the token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=[get_jwt_algorithm()],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat"],
            },
        )
    except jwt.ExpiredSignatureError:
        detail = "Token has expired"
        logger.warning("Email flow token expired")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
    except JWTError as e:
        detail = "Invalid token"
        logger.warning(f"Email flow token error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token type",
        )

    return payload


def create_auth_code(
    session_token: str,
    refresh_token: str | None = None,
) -> str:
    """Create a short-lived JWT auth code wrapping tokens.

    Used during OAuth callback redirects so the long-lived tokens
    are never exposed in the URL.  The auth code expires in 60 seconds.
    """
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "type": "auth_code",
        "jti": str(uuid.uuid4()),
        "session_token": session_token,
        "exp": now + timedelta(minutes=AUTH_CODE_EXPIRE_MINUTES),
        "iat": now,
    }
    if refresh_token:
        payload["refresh_token"] = refresh_token
    return jwt.encode(payload, get_secret_key(), algorithm=get_jwt_algorithm())


async def verify_auth_code(code: str) -> Dict[str, str]:
    """Verify a short-lived auth code and return the wrapped tokens.

    Returns a dict with ``session_token`` (always present) and
    ``refresh_token`` (present when the code was created with one).

    Each auth code can only be exchanged once (jti tracked in Redis).
    Raises HTTPException(400) if the code is invalid, expired, or already used.
    """
    try:
        payload = jwt.decode(code, get_secret_key(), algorithms=[get_jwt_algorithm()])
    except JWTError as e:
        logger.warning(f"Auth code verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired auth code",
        )

    if payload.get("type") != "auth_code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid auth code type",
        )

    # Enforce single-use via jti if present
    jti = payload.get("jti")
    if jti:
        try:
            from rhesis.backend.app.auth.used_token_store import claim_token_jti

            was_first_use = await claim_token_jti(jti, ttl_seconds=AUTH_CODE_EXPIRE_MINUTES * 60)
            if not was_first_use:
                logger.warning("Auth code replay attempt: jti=%s", jti)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Auth code already used",
                )
        except HTTPException:
            raise
        except Exception:
            # Redis unavailable -- log but allow through to avoid blocking
            # all logins when Redis is down
            logger.warning("Could not enforce single-use auth code (Redis unavailable)")

    session_token = payload.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth code missing session token",
        )

    result: Dict[str, str] = {"session_token": session_token}
    if payload.get("refresh_token"):
        result["refresh_token"] = payload["refresh_token"]

    return result


def generate_api_token() -> str:
    """Generate a secure API token in OpenAI-style format"""
    while True:
        token_bytes = secrets.token_bytes(32)
        token_b64 = base64.urlsafe_b64encode(token_bytes).decode("utf-8").rstrip("=")
        if "-" not in token_b64:
            return f"rh-{token_b64}"

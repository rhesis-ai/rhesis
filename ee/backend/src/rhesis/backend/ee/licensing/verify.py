"""JWT license token verification.

:func:`verify_token` is the public entry point.  It:

1. Decodes the JWT with EdDSA signature verification using the loaded public
   keys (``kid`` header selects the key).
2. Validates ``iss`` and ``aud`` against the shared constants in
   :mod:`~rhesis.backend.ee.licensing.entitlements`.
3. Parses the ``lic`` claim into an :class:`~rhesis.backend.ee.licensing.entitlements.Entitlements`
   instance — without checking expiry.
4. Caches the result (signature + structural validation is expensive; expiry
   is cheap and must be evaluated live on every call).

The cached result is keyed by the raw token string.  The provider calls
:meth:`~rhesis.backend.ee.licensing.entitlements.Entitlements.is_expired`
after every cache hit to enforce live expiry without re-doing crypto.

Returns ``None`` on any verification or parsing failure; callers fail closed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import jwt  # PyJWT

from rhesis.backend.ee.licensing.entitlements import (
    CLAIM_EXPIRY,
    CLAIM_JWT_ID,
    CLAIM_LICENSE,
    CLAIM_SUBJECT,
    LIC_ALL_FEATURES,
    LIC_EDITION,
    LIC_FEATURES,
    LIC_LIMITS,
    LIC_STATUS,
    LICENSE_ALGORITHM,
    LICENSE_AUDIENCE,
    LICENSE_ISSUER,
    REQUIRED_CLAIMS,
    Entitlements,
    LicenseEdition,
    LicenseStatus,
)
from rhesis.backend.ee.licensing.keys import get_public_keys

logger = logging.getLogger(__name__)

# PyJWT options: we decode exp into expires_at ourselves so the cache is not
# polluted by tokens that were valid at decode time but have since expired.
_DECODE_OPTIONS = {
    "verify_exp": False,  # expiry evaluated live by the caller
    "require": list(REQUIRED_CLAIMS),
}


@lru_cache(maxsize=256)
def _parse_token(raw_token: str) -> Optional[Entitlements]:
    """Parse and cryptographically verify *raw_token*, returning :class:`Entitlements`.

    Cached by raw token string — the expensive work (EdDSA sig verify +
    claim parsing) happens once per unique token value. Expiry is NOT
    checked here; callers must call :meth:`Entitlements.is_expired` live.

    Returns ``None`` on any failure.
    """
    public_keys = get_public_keys()
    if not public_keys:
        logger.warning("License verification skipped: no public keys loaded")
        return None

    # Peek at the kid header to select the right key.
    try:
        unverified_header = jwt.get_unverified_header(raw_token)
    except jwt.exceptions.InvalidTokenError as exc:
        logger.debug("License token header decode failed: %s", exc)
        return None

    kid = unverified_header.get("kid")
    if kid and kid in public_keys:
        candidate_keys = {kid: public_keys[kid]}
    else:
        # No kid or unknown kid — try all known keys (allows key rotation
        # where a new key arrives before the old token is replaced).
        candidate_keys = public_keys

    payload: Optional[dict] = None
    for _kid, pub_key in candidate_keys.items():
        try:
            payload = jwt.decode(
                raw_token,
                pub_key,
                algorithms=[LICENSE_ALGORITHM],
                audience=LICENSE_AUDIENCE,
                issuer=LICENSE_ISSUER,
                options=_DECODE_OPTIONS,
            )
            break
        except jwt.exceptions.InvalidSignatureError:
            # Wrong key for this token — the only key-dependent failure.
            # Try the next candidate (supports overlapping rotation windows).
            logger.debug("License token signature invalid for kid=%s; trying next key", _kid)
            continue
        except jwt.exceptions.InvalidTokenError as exc:
            # iss/aud mismatch, missing required claim, malformed payload, etc.
            # These are key-independent: retrying other keys cannot help, so
            # fail closed immediately. Catching the InvalidTokenError base
            # (not just DecodeError) is what keeps verification fail-closed
            # against the full PyJWT exception hierarchy.
            logger.debug("License token rejected (kid=%s): %s", _kid, exc)
            return None

    if payload is None:
        logger.debug("License token failed verification against all available keys")
        return None

    return _payload_to_entitlements(payload)


def _payload_to_entitlements(payload: dict) -> Optional[Entitlements]:
    """Map a decoded JWT payload dict to :class:`Entitlements`, or ``None`` on error."""
    try:
        lic: dict = payload.get(CLAIM_LICENSE) or {}

        exp_raw = payload.get(CLAIM_EXPIRY)
        expires_at: Optional[datetime] = None
        if exp_raw is not None:
            expires_at = datetime.fromtimestamp(int(exp_raw), tz=timezone.utc)

        return Entitlements(
            sub=str(payload[CLAIM_SUBJECT]),
            edition=LicenseEdition(lic.get(LIC_EDITION)),
            status=LicenseStatus(lic.get(LIC_STATUS)),
            all_features=bool(lic.get(LIC_ALL_FEATURES, False)),
            features=frozenset(str(f) for f in lic.get(LIC_FEATURES, [])),
            expires_at=expires_at,
            limits=dict(lic.get(LIC_LIMITS) or {}),
            jti=payload.get(CLAIM_JWT_ID),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("License token payload mapping failed: %s", exc)
        return None


def verify_token(raw_token: str) -> Optional[Entitlements]:
    """Verify *raw_token* and return live :class:`Entitlements` or ``None``.

    Uses the cached parse result and re-evaluates expiry on every call so
    tokens that expire while cached are correctly denied without a cache clear.
    """
    entitlements = _parse_token(raw_token)
    if entitlements is None:
        return None
    if entitlements.is_expired():
        logger.debug("License token for sub=%s is expired", entitlements.sub)
        return None
    return entitlements


__all__ = ["verify_token"]

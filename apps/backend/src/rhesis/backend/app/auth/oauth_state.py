"""Signed ``state`` parameters for outbound OAuth flows.

A ``state`` parameter travels to a third party and comes back, so it has to
carry the request's context without being forgeable. This signs a JSON payload
with HMAC-SHA256 over a key derived from ``SESSION_SECRET_KEY`` and encodes the
result base64url, which survives a round trip through any provider without
re-encoding.

Lifted from ``ee/sso/oidc.py``, where it served the SSO login flow alone. Two
changes came with the move:

- **The payload is the caller's.** The SSO version hardcoded ``org_id``,
  ``nonce`` and ``return_to``. Different flows carry different context.
- **The key is derived per purpose.** The SSO version derived one key from the
  literal ``"sso-state-"``. Sharing that across flows would make a state minted
  for one accepted by another, so a tool-connection state could be replayed
  into the SSO callback. ``purpose`` keeps the keys apart; passing ``"sso"``
  reproduces the original derivation byte for byte, so states already in flight
  stay valid.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any, Mapping

#: How long a state stays valid. Long enough to log in at the provider, short
#: enough that a leaked URL from a browser history is not a live credential.
DEFAULT_MAX_AGE_SECONDS = 300

_MIN_SECRET_LENGTH = 32


def _signing_key(purpose: str) -> bytes:
    """Derive the signing key for *purpose*.

    Raises ``RuntimeError`` when ``SESSION_SECRET_KEY`` is unset, so a
    misconfigured deployment fails loudly rather than silently signing with a
    constant key an attacker could reproduce.
    """
    session_key = os.getenv("SESSION_SECRET_KEY", "")
    if not session_key:
        raise RuntimeError(
            "SESSION_SECRET_KEY must be set before OAuth state signing can be used. "
            f"Set it to a random string of at least {_MIN_SECRET_LENGTH} characters."
        )
    return hashlib.sha256(f"{purpose}-state-{session_key}".encode()).digest()


def sign_state(payload: Mapping[str, Any], *, purpose: str) -> str:
    """Return a signed, base64url-encoded state carrying *payload*.

    A ``ts`` field is added and checked on the way back, so callers do not
    supply their own expiry.
    """
    body = {**payload, "ts": int(time.time())}
    data = json.dumps(body, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(_signing_key(purpose), data.encode(), hashlib.sha256).hexdigest()
    return urlsafe_b64encode(f"{data}|{sig}".encode()).decode()


def verify_state(
    state: str,
    *,
    purpose: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict:
    """Return the payload of a valid *state*, or raise ``ValueError``.

    Rejects anything that is not intact, not signed with *purpose*'s key, or
    older than *max_age_seconds*. The signature is compared in constant time.
    """
    try:
        # base64url may arrive with its padding stripped.
        padded = state + "=" * (-len(state) % 4)
        raw = urlsafe_b64decode(padded).decode()
    except Exception:
        raise ValueError("Invalid state encoding")

    if "|" not in raw:
        raise ValueError("Invalid state format")

    data, sig = raw.rsplit("|", 1)
    expected = hmac.new(_signing_key(purpose), data.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid state signature")

    payload = json.loads(data)
    if time.time() - payload.get("ts", 0) > max_age_seconds:
        raise ValueError("State parameter expired")

    return payload

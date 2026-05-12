"""EE implementation of the client-bound refresh-token minter.

Registered into core's :mod:`rhesis.backend.app.auth.refresh_client_hook`
single-slot registry from EE bootstrap. Core invokes this minter only
when the rotated refresh-token row carries a non-null ``client_id``.

Security checks performed here (each maps to an item in the threat
model documented on the orchestrator):

- HTTP Basic ``Authorization`` MUST be present and parseable.
- Decoded ``client_id`` MUST equal ``old_token.client_id`` -- a
  mismatch is an attempted lateral move from one client to another.
- ``client_secret`` MUST authenticate against the AuthClient row
  (constant-time, dummy-hash on miss inside ``authenticate_client``).
- AuthClient MUST NOT be ``disabled``.

If any check fails the minter raises :class:`HTTPException(401)` with
a generic detail. The detail string is identical across all failure
paths so that an attacker cannot probe whether (e.g.) the header was
absent vs the secret was wrong vs the client was disabled.

The freshly-minted access token re-uses the AuthClient's *current*
``token_epoch`` (not the value captured at issuance) so that a secret
rotation correctly invalidates the chain on its next refresh -- the
explicit revocation contract.
"""

from __future__ import annotations

import base64
import binascii
import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from rhesis.backend.app.auth.token_utils import create_session_token
from rhesis.backend.ee.api_clients.clients import authenticate_client

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.orm import Session

    from rhesis.backend.app.models.refresh_token import RefreshToken
    from rhesis.backend.app.models.user import User

logger = logging.getLogger(__name__)

# A single, shared HTTP 401 response body for every failure mode. We
# deliberately do not vary the detail string with the failure reason
# because doing so would let a caller distinguish (for example) a
# missing header from a wrong secret -- exactly the oracle the
# constant-time client lookup is designed to deny.
_INVALID_CLIENT_DETAIL = "Invalid client credentials"


def _raise_401() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_INVALID_CLIENT_DETAIL,
    )


def _decode_basic_auth(header: str) -> tuple[str, str]:
    """Return ``(client_id, client_secret)`` from an HTTP Basic header.

    Returns ``("", "")`` and lets the caller raise on any structural
    failure -- centralising the raise keeps the failure-mode oracle
    closed at one site.
    """
    try:
        scheme, encoded = header.split(" ", 1)
    except ValueError:
        return "", ""
    if scheme.lower() != "basic":
        return "", ""
    try:
        raw = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return "", ""
    if ":" not in raw:
        return "", ""
    cid, secret = raw.split(":", 1)
    if not cid or not secret:
        return "", ""
    return cid, secret


def mint_for_client_bound_refresh(
    db: "Session",
    request: "Request",
    old_token: "RefreshToken",
    user: "User",
) -> str:
    """Authenticate the calling AuthClient and mint a client-bound JWT.

    See module docstring for the full security contract. This is the
    function registered into
    :func:`rhesis.backend.app.auth.refresh_client_hook.register_refresh_client_minter`
    by EE bootstrap.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header:
        _raise_401()
    assert auth_header is not None  # narrow for the type checker

    client_id, client_secret = _decode_basic_auth(auth_header)
    if not client_id:
        _raise_401()

    # Block lateral movement: the credential presented MUST be for
    # the exact same client that minted the original refresh token.
    if client_id != old_token.client_id:
        _raise_401()

    auth_client = authenticate_client(db, client_id, client_secret)
    if auth_client is None or auth_client.disabled:
        _raise_401()
    assert auth_client is not None  # narrow for the type checker

    # Mint with the AuthClient's *current* token_epoch so a secret
    # rotation invalidates the chain on its next refresh.
    return create_session_token(
        user,
        azp=auth_client.client_id,
        scope=old_token.scope,
        epoch=auth_client.token_epoch,
    )


__all__ = ["mint_for_client_bound_refresh"]

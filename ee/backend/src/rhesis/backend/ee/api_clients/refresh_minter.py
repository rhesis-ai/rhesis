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
- AuthClient ``organization_id`` MUST equal the bound user's
  ``organization_id``. If a user moved orgs between issuance and
  refresh (rare but possible), the original (user, client) binding
  is no longer coherent and must not silently mint a fresh JWT.

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

    # Org-scope the lookup using the bound user's org. Two tenants may
    # share a client_id (per-org unique constraint), so passing
    # client_id alone would risk authenticating against the wrong
    # row. The user's org is the authoritative scope here because the
    # refresh row was minted for this exact (user, client) pair.
    auth_client = authenticate_client(
        db, user.organization_id, client_id, client_secret
    )
    if auth_client is None or auth_client.disabled:
        _raise_401()
    assert auth_client is not None  # narrow for the type checker

    # Defence in depth: the org-scoped lookup above already filters by
    # ``user.organization_id``, so a row from a different org cannot
    # be returned. Re-asserting the invariant here makes the contract
    # explicit so a future refactor of authenticate_client cannot
    # accidentally widen the scope without this check tripping in
    # tests first.
    if str(auth_client.organization_id) != str(user.organization_id):
        _raise_401()

    # Mint with the AuthClient's *current* token_epoch so a secret
    # rotation invalidates the chain on its next refresh.
    #
    # Strip ``offline_access`` from the access token's scope claim --
    # it's an OIDC convention for "give me a refresh token", not an
    # authority. The refresh row still carries it (so re-rotation
    # preserves the original intent) and is consulted on the next
    # refresh; only the access token's scope is filtered.
    access_scope = _strip_offline_access(old_token.scope)
    return create_session_token(
        user,
        azp=auth_client.client_id,
        scope=access_scope,
        epoch=auth_client.token_epoch,
    )


def _strip_offline_access(scope: str | None) -> str | None:
    """Return *scope* with the ``offline_access`` token removed.

    Keeps order and other tokens intact. Returns ``None`` when the
    input is ``None`` so callers that pass ``old_token.scope``
    unchanged for UI/SSO refresh tokens (NULL scope) keep the
    historical behaviour.
    """
    if not scope:
        return scope
    parts = [p for p in scope.split(" ") if p and p != "offline_access"]
    return " ".join(parts) if parts else None


__all__ = ["mint_for_client_bound_refresh"]

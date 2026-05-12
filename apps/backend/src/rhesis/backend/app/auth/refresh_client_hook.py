"""Extension point for client-bound refresh-token minting.

``/auth/refresh`` in core mints a plain session token for UI / SSO
refresh tokens (``RefreshToken.client_id IS NULL``). When a refresh
row carries a ``client_id`` it was issued via the EE
``/auth/token-exchange`` flow, and the refresh path has to:

- require HTTP Basic ``Authorization`` from the same client,
- verify the client_secret against the AuthClient row,
- re-mint the access token with the binding claims
  (``azp`` / ``aud`` / ``scope`` / ``epoch``).

All three steps depend on :class:`AuthClient`, which is an EE
concept. To keep core's ``/auth/refresh`` MIT-clean, EE registers a
*minter* via this module at bootstrap time; core invokes it via
:func:`get_refresh_client_minter` only when the refresh row has a
non-null client_id.

The contract
------------
A *minter* is ``Callable[[Session, Request, RefreshToken, User], str]``:

- ``Session`` is the active DB session (already mid-transaction;
  the minter must not commit / rollback).
- ``Request`` carries the ``Authorization`` header to inspect.
- ``RefreshToken`` is the **old** row (pre-rotation) with
  ``client_id`` and ``scope`` populated; the minter trusts these
  fields unconditionally because the rotation step already verified
  the row's authenticity.
- ``User`` is the resolved user.

The minter raises :class:`fastapi.HTTPException` to reject (401 / 503
as appropriate) and returns the access-token string on success.

Why a single-slot registry rather than a list?
----------------------------------------------
There is exactly one valid behaviour for a client-bound refresh:
verify the AuthClient credential and re-mint. Stacking enrichers
would invite two implementations to silently disagree about which
one minted the token, which is the threat the binding exists to
prevent in the first place. A single slot makes the configuration
mistake (two registrants) loud at startup.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.orm import Session

    from rhesis.backend.app.models.refresh_token import RefreshToken
    from rhesis.backend.app.models.user import User

logger = logging.getLogger(__name__)

#: Signature of the registered refresh minter.
RefreshClientMinter = Callable[
    ["Session", "Request", "RefreshToken", "User"], str
]

_minter: Optional[RefreshClientMinter] = None


def register_refresh_client_minter(minter: RefreshClientMinter) -> None:
    """Install *minter* as the handler for client-bound refresh tokens.

    Idempotent for the *same* callable (so a bootstrap that runs
    twice in a test run is safe) but loud for a *different* one
    (so a misconfigured deployment with two competing implementations
    fails immediately rather than silently using the second registrant).
    """
    global _minter
    if _minter is minter:
        return
    if _minter is not None:
        raise RuntimeError(
            "refresh_client_minter already registered; refusing to "
            "replace -- see refresh_client_hook.py for rationale"
        )
    _minter = minter
    logger.info("Refresh-client minter registered: %s", minter.__qualname__)


def get_refresh_client_minter() -> Optional[RefreshClientMinter]:
    """Return the registered minter, or ``None`` when EE is absent.

    Core uses ``None`` as the signal to fall back to the legacy
    minter for UI / SSO refresh tokens, and as the trigger to
    reject (with 503) any client-bound refresh token presented in
    a Community-only deployment that should not have produced one.
    """
    return _minter


def reset_refresh_client_minter() -> None:
    """Test-only: clear the registered minter."""
    global _minter
    _minter = None


__all__ = [
    "RefreshClientMinter",
    "get_refresh_client_minter",
    "register_refresh_client_minter",
    "reset_refresh_client_minter",
]

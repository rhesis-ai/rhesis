"""Map RFC 8693 token-exchange OAuth scope claims to capability sets.

Token-exchange-issued JWTs (``ee/backend/.../token_exchange/exchange.py``)
carry a coarse OAuth ``scope`` claim -- v1 supports ``read`` and ``full``
(``ee/backend/.../api_clients/schemas.py:V1_SUPPORTED_SCOPES``;
``offline_access`` never reaches this claim, ``exchange.py`` strips it before
minting the access token). This module translates that claim into the
fine-grained capability vocabulary (``"resource:action"``) that
:class:`~rhesis.backend.app.auth.principal.Principal.scopes` and the EE RBAC
provider actually consume, so a project-scoped API client requesting ``read``
is limited to read-only access instead of silently inheriting its owner's
full access.

Deliberately lives in core, not ``ee.*``: the mapping is generic
capability-catalog logic, no different from how the ``rh-*`` token path
already stores its ``scopes`` column directly as capability strings. The
literal ``"read"`` / ``"full"`` scope names are just strings here, so this
file creates no community-boundary import.

Enforcement note: :class:`~rhesis.backend.ee.rbac.provider.PermissionAuthorizationProvider`
only consults ``Principal.scopes`` when RBAC is licensed for the org
(``rbac_active_for``); otherwise it falls back to
:class:`~rhesis.backend.app.auth.rbac.DefaultAuthorizationProvider`, which
never reads ``scopes`` at all. Setting the field here is correct either way
-- inert where RBAC isn't active, effective where it is -- so this module
does not need to check RBAC availability itself.
"""

from __future__ import annotations

from typing import Optional


def capabilities_for_oauth_scope(scope_claim: Optional[str]) -> Optional[frozenset[str]]:
    """Return the capability set an OAuth ``scope`` claim grants.

    Returns ``None`` for ``full`` (checked first, so ``"read full"`` also
    resolves to unrestricted) -- the same sentinel
    :class:`~rhesis.backend.app.auth.principal.Principal.scopes` uses for
    "inherit the owner's full access", matching an unscoped ``rh-*`` token.

    Returns the frozenset of every registered ``*:read`` capability for
    ``read`` alone.

    Returns an empty frozenset -- not ``None`` -- when *scope_claim* is
    ``None``, empty, or carries no recognized access-granting scope (e.g. a
    token minted for ``offline_access`` only, which strips to an empty scope
    string). Fail-closed: an unrecognized or absent scope grants nothing,
    never everything.
    """
    tokens = set((scope_claim or "").split())
    if "full" in tokens:
        return None
    if "read" in tokens:
        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        return frozenset(cap for cap in get_all_capabilities() if cap.endswith(":read"))
    return frozenset()


__all__ = ["capabilities_for_oauth_scope"]

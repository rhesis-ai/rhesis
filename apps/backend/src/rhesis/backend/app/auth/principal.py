"""Principal — unified caller identity for authorization.

Resolves an authenticated User into a Principal once per request so that
``authorize()`` and the PEP backstop (SP4) never branch on user-vs-token.

Phase 1 (community): all authenticated callers are session principals; the
token boundary (``token_project_id``) and fine-grained ``scopes`` fields are
reserved for EE Phase 2 (SP9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional
from uuid import UUID

# Keys used to stash token context on request.state in user_utils.py.
# Centralised here so callers share the same string literals.
REQUEST_STATE_AUTH_KIND = "auth_kind"
REQUEST_STATE_API_TOKEN_SCOPES = "api_token_scopes"
REQUEST_STATE_API_TOKEN_PROJECT_ID = "api_token_project_id"


@dataclass(frozen=True)
class Principal:
    """Immutable caller identity resolved once at the start of authorization.

    Attributes:
        user_id: The authenticated user's UUID.
        organization_id: The user's active organization UUID.  ``None`` only
            during the brief onboarding window before an org has been created;
            all authorization checks fail-closed when it is ``None``.
        kind: ``"session"`` for browser/JWT sessions; ``"token"`` for ``rh-*``
            API tokens and EE M2M clients.
        scopes: EE Phase 2 (SP9) — explicit permission subset carried by the
            token.  ``None`` in community mode (inherit owner's full access).
        token_project_id: EE Phase 2 (SP9) — single-project boundary of the
            issuing token.  ``None`` means the token is not project-restricted.
    """

    user_id: UUID
    organization_id: Optional[UUID]
    kind: Literal["session", "token"]
    # Populated in EE Phase 2 (SP9); intentionally excluded from equality so
    # two Principals for the same user compare equal regardless of token scopes.
    scopes: Optional[frozenset[str]] = field(default=None, compare=False)
    token_project_id: Optional[UUID] = field(default=None, compare=False)


def resolve_principal(
    user: "object",
    *,
    scopes: Optional[frozenset[str]] = None,
    token_project_id: Optional[UUID] = None,
    kind: "Literal['session', 'token']" = "session",
) -> Principal:
    """Build a :class:`Principal` from an authenticated ``User`` ORM object.

    Phase 2 (SP9): pass ``scopes`` and ``token_project_id`` when the request
    was authenticated via an API token that carries explicit scope restrictions.
    The PEP backstop reads these from ``request.state`` (set by
    ``get_authenticated_user_with_context``) and forwards them here.

    Args:
        user: An authenticated ``models.User`` instance as returned by
            ``require_current_user_or_token``.
        scopes: Optional explicit permission subset from the authenticating
            token (SP9).  ``None`` means the token inherits the owner's full
            access (no scope narrowing).
        token_project_id: Optional single-project boundary of the token (SP9).
        kind: ``"token"`` when the request was authenticated via an API token
            or M2M client JWT; ``"session"`` otherwise.

    Returns:
        A frozen :class:`Principal` ready to pass to
        :func:`~rhesis.backend.app.auth.rbac.authorize`.
    """
    return Principal(
        user_id=user.id,  # type: ignore[attr-defined]
        organization_id=user.organization_id,  # type: ignore[attr-defined]
        kind=kind,
        scopes=scopes,
        token_project_id=token_project_id,
    )


def resolve_principal_from_request(user: "object", request: "object") -> Principal:
    """Build a :class:`Principal` reading token context from ``request.state``.

    Drop-in replacement for ``resolve_principal(user)`` in FastAPI handlers that
    receive a ``Request`` object.  Reads ``auth_kind``, ``api_token_scopes``, and
    ``api_token_project_id`` from ``request.state`` so the Principal accurately
    reflects an unscoped token (``kind="token"`` with ``scopes=None``) rather than
    being silently misclassified as ``kind="session"``.
    """
    from uuid import UUID

    token_scopes = getattr(request.state, REQUEST_STATE_API_TOKEN_SCOPES, None)  # type: ignore[union-attr]
    token_project_id_str = getattr(request.state, REQUEST_STATE_API_TOKEN_PROJECT_ID, None)  # type: ignore[union-attr]
    auth_kind = getattr(request.state, REQUEST_STATE_AUTH_KIND, "session")  # type: ignore[union-attr]
    token_project_id: Optional[UUID] = None
    if token_project_id_str:
        try:
            token_project_id = UUID(token_project_id_str)
        except (ValueError, AttributeError):
            pass
    return resolve_principal(
        user,
        scopes=token_scopes,
        token_project_id=token_project_id,
        kind=auth_kind,
    )


__all__ = [
    "Principal",
    "REQUEST_STATE_AUTH_KIND",
    "REQUEST_STATE_API_TOKEN_PROJECT_ID",
    "REQUEST_STATE_API_TOKEN_SCOPES",
    "resolve_principal",
    "resolve_principal_from_request",
]

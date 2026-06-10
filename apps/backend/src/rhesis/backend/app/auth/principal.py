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


def resolve_principal(user: "object") -> Principal:
    """Build a :class:`Principal` from an authenticated ``User`` ORM object.

    Phase 1: all authenticated users are treated as session principals with no
    scope restrictions.  The ``kind`` argument may be overridden by the token
    authentication path in Phase 2 once we distinguish session vs. token callers
    in ``auth/user_utils.py``.

    Args:
        user: An authenticated ``models.User`` instance as returned by
            ``require_current_user_or_token``.

    Returns:
        A frozen :class:`Principal` ready to pass to :func:`~rhesis.backend.app.auth.rbac.authorize`.
    """
    return Principal(
        user_id=user.id,  # type: ignore[attr-defined]
        organization_id=user.organization_id,  # type: ignore[attr-defined]
        kind="session",
    )


__all__ = ["Principal", "resolve_principal"]

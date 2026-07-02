"""Extension point for privilege-escalation checks on project-role assignment.

Graded roles are an EE concept (``role_id`` on ``project_membership`` is an FK
placeholder in core; the role catalog and the escalation guard live in EE).  The
community ``POST /projects/{id}/members`` endpoint accepts an optional
``role_id`` so a member can be added *with* a role in a single atomic request,
but core must never import EE (``community-boundary`` CI job) and must not grant
a role without the same privilege-escalation guard the EE
``PUT /rbac/.../role`` endpoint enforces.

So core exposes this tiny validator registry and EE registers a handler in its
:func:`~rhesis.backend.ee.bootstrap`.  Core calls
:func:`validate_project_role_assignment` from ``add_project_member`` *only when a
``role_id`` is supplied*.

Contract
--------
A validator is ``Callable[[Session, User, UUID, UUID], None]`` receiving
``(db, actor, role_id, project_id)``.  It must raise ``HTTPException`` (403 on
escalation, 404 on unknown role, 422 on an unassignable role) to reject the
assignment, and return ``None`` to allow it.  It must not commit / rollback.

Fail-closed when unregistered
------------------------------
If ``role_id`` is provided but no validator is registered — a community-only
build, or RBAC not licensed — :func:`validate_project_role_assignment` raises
422.  Community has no graded roles, so accepting a ``role_id`` there is
meaningless; silently dropping it would hide the caller's intent.  Adding a
member *without* a ``role_id`` never calls this and is unaffected.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, List
from uuid import UUID

from fastapi import HTTPException

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from rhesis.backend.app.models.user import User

logger = logging.getLogger(__name__)

#: Signature for a project-role-assignment validator.
RoleAssignmentValidator = Callable[["Session", "User", UUID, UUID], None]

_validators: List[RoleAssignmentValidator] = []


def register_role_assignment_validator(validator: RoleAssignmentValidator) -> None:
    """Register *validator* to gate project-role assignment at member-add time.

    Idempotent: re-registering the same callable is a no-op, so an EE bootstrap
    that runs multiple times across a test suite is safe.
    """
    if validator not in _validators:
        _validators.append(validator)
        logger.debug(
            "role-assignment validator registered: %s",
            getattr(validator, "__qualname__", repr(validator)),
        )


def validate_project_role_assignment(
    db: "Session", actor: "User", role_id: UUID, project_id: UUID
) -> None:
    """Run every registered validator for assigning *role_id* on *project_id*.

    Called by core from ``add_project_member`` only when a ``role_id`` is
    supplied.  Raises 422 when no validator is registered (community build /
    RBAC unlicensed), since a graded role cannot be honored there.  Any
    validator may raise ``HTTPException`` to reject the assignment.
    """
    if not _validators:
        raise HTTPException(
            status_code=422,
            detail="Assigning a role requires RBAC, which is not enabled for this organization",
        )
    for validator in _validators:
        validator(db, actor, role_id, project_id)


def reset_role_assignment_validators() -> None:
    """Clear all registered validators. For tests only."""
    _validators.clear()


__all__ = [
    "RoleAssignmentValidator",
    "register_role_assignment_validator",
    "validate_project_role_assignment",
    "reset_role_assignment_validators",
]

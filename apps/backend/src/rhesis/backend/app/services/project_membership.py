"""Reading and writing a caller's project memberships.

Discovery (``list_other_member_projects``) is shared by any endpoint that needs
to search across a caller's OTHER projects under real RLS scope
(project_isolation is FORCE-enabled and keyed on the `app.current_project` GUC,
so a lookup scoped to the active project cannot see rows in a different one —
see ``routers/resolve.py`` for the full rationale). ``project_membership``
carries no ``project_isolation`` policy (dropped intentionally in the
``b8c9d0e1f2a3`` migration), so it's queryable at org scope; wrapped in
``bypass_tenant_filter()`` only because it *does* have a ``project_id`` column
that the ORM auto-filter would otherwise pin to the active project.

The enroll/unenroll functions additionally keep each affected user's
``default_project`` setting pointing at a project they can still reach, and bust
the permission cache so a membership change takes effect on the next
``authorize()`` call rather than waiting out the TTL.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models
from rhesis.backend.app.scope import bypass_tenant_filter

_logger = logging.getLogger(__name__)


def list_other_member_projects(
    db: Session,
    organization_id: str,
    user_id: str,
    exclude_project_id: str | None = None,
) -> list[tuple[str, str]]:
    """Return (project_id, project_name) for every ACTIVE, non-deleted project
    the caller belongs to in this org, excluding ``exclude_project_id``
    (typically the active one).
    """
    with bypass_tenant_filter():
        rows = (
            db.query(models.Project.id, models.Project.name)
            .join(
                models.ProjectMembership,
                models.ProjectMembership.project_id == models.Project.id,
            )
            .filter(
                models.ProjectMembership.user_id == user_id,
                models.ProjectMembership.organization_id == organization_id,
                models.Project.deleted_at.is_(None),
                models.Project.is_active.is_(True),
            )
            .all()
        )

    return [(str(pid), name) for pid, name in rows if str(pid) != (exclude_project_id or "")]


# ---------------------------------------------------------------------------
# Service-layer exceptions
# ---------------------------------------------------------------------------


class ProjectServiceError(Exception):
    """Base class for project membership service errors."""


class ProjectOwnerRemovalError(ProjectServiceError):
    """Raised when attempting to remove the project owner from a project."""


class ProjectSelfRemovalError(ProjectServiceError):
    """Raised when the requesting user attempts to remove themselves from a project."""


# ---------------------------------------------------------------------------


def _set_default_project_if_empty(db: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
    """Set the user's default_project setting to this project if they have none.

    Never clobbers an existing default. Stores {"id", "name"} so the frontend can
    display the name without an extra lookup.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        return
    if user.settings.default_project is not None:
        return
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project is None:
        return
    user.settings.update({"default_project": {"project_id": str(project.id), "name": project.name}})
    flag_modified(user, "user_settings")


def _reassign_default_project_if_removed(
    db: Session,
    user_id: uuid.UUID,
    removed_project_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> None:
    """If the removed project was the user's default, repoint or clear the default.

    Picks the user's earliest remaining membership; clears the setting if none remain.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        return
    current = user.settings.default_project
    current_pid = current.get("project_id") or current.get("id") if current else None
    if not current_pid or str(current_pid) != str(removed_project_id):
        return

    remaining = (
        db.query(models.Project)
        .join(models.ProjectMembership, models.ProjectMembership.project_id == models.Project.id)
        .filter(
            models.ProjectMembership.user_id == user_id,
            models.ProjectMembership.organization_id == organization_id,
            models.ProjectMembership.project_id != removed_project_id,
        )
        .order_by(models.Project.created_at.asc())
        .first()
    )
    if remaining is not None:
        user.settings.update(
            {"default_project": {"project_id": str(remaining.id), "name": remaining.name}}
        )
    else:
        settings = user.settings.raw
        settings.pop("default_project", None)
        user.user_settings = settings
    flag_modified(user, "user_settings")


def _bust_permission_cache(user_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    """Bust the permission cache for *user_id* within *organization_id*.

    Called after any project-membership write so the next ``authorize()`` call
    re-evaluates against the database rather than returning a stale cached result.
    Failures are logged but never re-raised — a cache-bust error degrades to
    relying on the TTL, not to a service error.
    """
    try:
        from rhesis.backend.app.services.permission_cache import get_permission_cache

        get_permission_cache().bust_user(user_id, organization_id)
    except Exception as exc:  # pragma: no cover
        _logger.warning(
            "permission cache bust failed for user %s org %s (non-fatal): %s",
            user_id,
            organization_id,
            exc,
        )


def enroll_user_in_project(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    *,
    role_id: Optional[uuid.UUID] = None,
) -> None:
    """Enroll a user in a project and set their default_project if unset.

    Uses INSERT … ON CONFLICT DO NOTHING so concurrent enrollments for the same
    (project_id, user_id) pair are safe — the unique constraint
    ``uq_project_membership_project_user`` silently absorbs the duplicate rather
    than raising an IntegrityError.

    ``role_id`` is an optional FK placeholder for the EE role table (SP8).  In
    community mode it is always ``None`` (binary membership).  Phase 2 will pass
    a real role UUID here when inviting users with an explicit role.

    Executes the INSERT immediately within the current transaction; the caller is
    still responsible for committing (or rolling back).

    Busts the permission cache for *user_id* so the next ``authorize()`` call
    re-evaluates against the database (plan §1.6 / §8b revocation requirement).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # role_id is nullable; passing None inserts a binary (no-role) membership.
    stmt = (
        pg_insert(models.ProjectMembership)
        .values(
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            role_id=role_id,
        )
        .on_conflict_do_nothing(constraint="uq_project_membership_project_user")
    )
    db.execute(stmt)

    # _set_default_project_if_empty does db.query() calls; bypass the ambient
    # project/org filter so the user and project are always found.
    with bypass_tenant_filter():
        _set_default_project_if_empty(db, user_id, project_id)

    _bust_permission_cache(user_id, organization_id)


def unenroll_user_from_project(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    *,
    requester_user_id: Optional[uuid.UUID] = None,
) -> bool:
    """Remove a user's ProjectMembership and repair their default_project if needed.

    Raises:
        ProjectSelfRemovalError: if requester_user_id matches user_id (self-removal).
        ProjectOwnerRemovalError: if user_id is the project owner.

    Returns True if a membership was removed, False if none existed. Does NOT
    commit; the caller is responsible for committing.

    Busts the permission cache for *user_id* so the revocation takes effect on
    the next ``authorize()`` call rather than waiting out the TTL (plan §8b).
    """
    with bypass_tenant_filter():
        # Self-removal guard — checked here so non-HTTP callers also get the protection.
        if requester_user_id is not None and str(requester_user_id) == str(user_id):
            raise ProjectSelfRemovalError("A user cannot remove themselves from a project")

        # Owner guard — query the project to check owner_id.
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if project and project.owner_id and str(project.owner_id) == str(user_id):
            raise ProjectOwnerRemovalError("The project owner cannot be removed from a project")

        membership = (
            db.query(models.ProjectMembership)
            .filter_by(
                project_id=project_id,
                user_id=user_id,
                organization_id=organization_id,
            )
            .first()
        )
        if membership is None:
            return False

        # Hard delete (not soft delete): the uq_project_membership_project_user
        # unique constraint would otherwise block re-enrolling the same user.
        db.delete(membership)
        _reassign_default_project_if_removed(db, user_id, project_id, organization_id)

    _bust_permission_cache(user_id, organization_id)
    return True


def unenroll_all_project_members(
    db: Session,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> int:
    """
    Remove every ProjectMembership for a project and repair affected users' defaults.

    Intended for project deletion: project soft-delete does not cascade to the
    membership table, so without this the rows are orphaned and users keep a
    default_project pointing at a dead project. Returns the number of memberships
    removed. Does NOT commit; the caller is responsible for committing.

    Busts the permission cache for every removed member (plan §8b).
    """
    with bypass_tenant_filter():
        memberships = (
            db.query(models.ProjectMembership)
            .filter_by(project_id=project_id, organization_id=organization_id)
            .all()
        )
        user_ids = [m.user_id for m in memberships]
        for membership in memberships:
            db.delete(membership)
        # Flush the deletes so the per-user default repair sees the rows as gone
        # when it scans for a replacement membership.
        db.flush()
        for user_id in user_ids:
            _reassign_default_project_if_removed(db, user_id, project_id, organization_id)

    for user_id in user_ids:
        _bust_permission_cache(user_id, organization_id)

    return len(user_ids)

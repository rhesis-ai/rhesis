"""CRUD operations for projects and project membership.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

Project reads enforce membership, not just organization scope -- ``get_project`` and
``get_projects`` return only projects the caller has a ``project_membership`` row for.
Writes to membership route through ``services.organization`` so that a user's
``default_project`` is repaired alongside.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import include


def get_project(
    db: Session, project_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Project]:
    """Get project with relationships eagerly loaded.

    When *user_id* is supplied the caller must be an explicit member of the project
    (a row in ``project_membership``).  Non-members receive ``None`` — the same
    result as "not found" — so the router's 404 reveals no information about
    whether the project exists.  This closes the by-ID IDOR gap where
    ``get_item_detail`` filters only by ``organization_id``.

    Pass *user_id=None* only for internal service-layer calls that already
    carry their own access-control context (e.g. background tasks).
    """
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.app.scope import bypass_tenant_filter

    project = get_item_detail(db, models.Project, project_id, organization_id, user_id)
    if project is None or user_id is None:
        return project

    # Enforce membership: the caller must have a project_membership row.
    # bypass_tenant_filter is required because project_membership carries only
    # tenant_isolation (org RLS), not project_isolation — this is by design so
    # the join table remains reachable before a project context is established.
    with bypass_tenant_filter():
        membership = (
            db.query(ProjectMembership).filter_by(project_id=project.id, user_id=user_id).first()
        )

    return project if membership is not None else None


def get_projects(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Project]:
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.app.utils.query_utils import QueryBuilder

    # Project listing must respect membership — only return projects the requesting
    # user is a member of. An EXISTS subquery is used so that the QueryBuilder's
    # existing pagination/sorting/filtering chain is preserved.
    with bypass_tenant_filter():
        builder = (
            QueryBuilder(db, models.Project)
            .with_related(include(models.Project.owner))
            .with_default_derived_field_loads()
            .with_organization_filter(organization_id)
            .with_visibility_filter(user_id)
            .with_odata_filter(filter)
        )

        if user_id:
            exists_subquery = (
                db.query(ProjectMembership)
                .filter(
                    ProjectMembership.project_id == models.Project.id,
                    ProjectMembership.user_id == user_id,
                    ProjectMembership.organization_id == organization_id,
                )
                .exists()
            )
            builder.query = builder.query.filter(exists_subquery)

        return builder.with_pagination(skip, limit).with_sorting(sort_by, sort_order).all()


def count_projects(
    db: Session,
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> int:
    """Count projects the given user is a member of (mirrors get_projects membership filter)."""
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.app.utils.query_utils import QueryBuilder

    with bypass_tenant_filter():
        builder = (
            QueryBuilder(db, models.Project)
            .with_organization_filter(organization_id)
            .with_visibility_filter(user_id)
            .with_odata_filter(filter)
        )
        if user_id:
            exists_subquery = (
                db.query(ProjectMembership)
                .filter(
                    ProjectMembership.project_id == models.Project.id,
                    ProjectMembership.user_id == user_id,
                    ProjectMembership.organization_id == organization_id,
                )
                .exists()
            )
            builder.query = builder.query.filter(exists_subquery)
        return builder.count()


def create_project(
    db: Session, project: schemas.ProjectCreate, organization_id: str = None, user_id: str = None
) -> models.Project:
    """Create project."""
    return create_item(db, models.Project, project, organization_id, user_id)


def update_project(
    db: Session,
    project_id: uuid.UUID,
    project: schemas.ProjectUpdate,
    organization_id: str,
    user_id: str,
) -> Optional[models.Project]:
    return update_item(db, models.Project, project_id, project, organization_id, user_id)


def delete_project(
    db: Session, project_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Project]:
    # Project soft-delete does not cascade to project_membership, so drop the
    # memberships and repair affected users' default_project first. Staged in the
    # same transaction; delete_item's commit persists both.
    from rhesis.backend.app.services.organization import unenroll_all_project_members

    unenroll_all_project_members(db, project_id, organization_id)
    return delete_item(
        db, models.Project, project_id, organization_id=organization_id, user_id=user_id
    )


# ProjectMembership CRUD


def get_project_members(
    db: Session, project_id: uuid.UUID, organization_id: str
) -> List[models.ProjectMembership]:
    """List all members of a project, with user info eagerly loaded."""
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.app.models.user import User
    from rhesis.backend.app.scope import bypass_tenant_filter

    # Explicitly scoped by (project_id, organization_id); bypass the ambient project
    # filter so listing works regardless of which project is currently active.
    with bypass_tenant_filter():
        return (
            db.query(ProjectMembership)
            .join(User, ProjectMembership.user_id == User.id)
            .filter(
                ProjectMembership.project_id == project_id,
                ProjectMembership.organization_id == organization_id,
            )
            .options(joinedload(ProjectMembership.user))
            .all()
        )


def get_my_projects(db: Session, user_id: uuid.UUID, organization_id: str) -> List[models.Project]:
    """Return all ACTIVE, non-deleted projects the given user is a member of."""
    from rhesis.backend.app.models.project_membership import ProjectMembership

    return (
        db.query(models.Project)
        .options(include(models.Project.owner))
        .join(ProjectMembership, ProjectMembership.project_id == models.Project.id)
        .filter(
            ProjectMembership.user_id == user_id,
            ProjectMembership.organization_id == organization_id,
            models.Project.deleted_at.is_(None),
            models.Project.is_active.is_(True),
        )
        .all()
    )


def add_project_member(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    organization_id: str,
    *,
    role_id: Optional[uuid.UUID] = None,
) -> models.ProjectMembership:
    """Add a user as a project member. No-op (returns existing) if already a member.

    Routes through the centralized enroll_user_in_project routine so that membership
    creation and default-project assignment stay consistent with onboarding.

    ``role_id`` is an optional FK placeholder for the EE role table (SP8).  Passes
    through to ``enroll_user_in_project``; community callers leave it ``None``.
    """
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.app.services.organization import enroll_user_in_project

    with bypass_tenant_filter():
        existing = (
            db.query(ProjectMembership).filter_by(project_id=project_id, user_id=user_id).first()
        )
    if existing:
        return existing

    enroll_user_in_project(db, user_id, project_id, organization_id, role_id=role_id)
    db.commit()

    with bypass_tenant_filter():
        return db.query(ProjectMembership).filter_by(project_id=project_id, user_id=user_id).first()


def remove_project_member(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    organization_id: str,
    *,
    requester_user_id: Optional[uuid.UUID] = None,
) -> bool:
    """Remove a user from a project. Returns True if removed, False if not found.

    Routes through the centralized unenroll_user_from_project routine so that the
    user's default_project is repaired if it pointed at the removed project.

    Raises:
        ProjectSelfRemovalError: if requester_user_id == user_id.
        ProjectOwnerRemovalError: if user_id is the project owner.
    """
    from rhesis.backend.app.services.organization import unenroll_user_from_project

    removed = unenroll_user_from_project(
        db, user_id, project_id, organization_id, requester_user_id=requester_user_id
    )
    if removed:
        db.commit()
    return removed

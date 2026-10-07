"""CRUD operations for project memberships.

Memberships are hard deleted: the ``uq_project_membership_project_user`` unique
constraint would otherwise block re-enrolling the same user. Callers run these
inside ``bypass_tenant_filter()`` and own the commit.
"""

import uuid
from typing import List, Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rhesis.backend.app import models


def add_membership(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role_id: Optional[uuid.UUID] = None,
) -> Optional[uuid.UUID]:
    """Insert a membership unless one exists; return the new row's id, or None.

    ON CONFLICT DO NOTHING keeps concurrent enrollments of the same pair safe.
    """
    stmt = (
        pg_insert(models.ProjectMembership)
        .values(
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            role_id=role_id,
        )
        .on_conflict_do_nothing(constraint="uq_project_membership_project_user")
        .returning(models.ProjectMembership.id)
    )
    return db.scalars(stmt).first()


def delete_membership(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID, organization_id: uuid.UUID
) -> bool:
    """Delete one user's membership of a project; False if there was none."""
    membership = (
        db.query(models.ProjectMembership)
        .filter_by(project_id=project_id, user_id=user_id, organization_id=organization_id)
        .first()
    )
    if membership is None:
        return False
    db.delete(membership)
    return True


def delete_project_memberships(
    db: Session, project_id: uuid.UUID, organization_id: uuid.UUID
) -> List[uuid.UUID]:
    """Delete every membership of a project and flush; return the removed user ids."""
    memberships = (
        db.query(models.ProjectMembership)
        .filter_by(project_id=project_id, organization_id=organization_id)
        .all()
    )
    for membership in memberships:
        db.delete(membership)
    db.flush()
    return [m.user_id for m in memberships]

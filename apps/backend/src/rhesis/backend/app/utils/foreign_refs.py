"""Check foreign ids in a write payload against the caller's organization.

Stamping only fills tenant columns that are missing; it never checks a supplied id.
The ``user`` table has no RLS and is skipped by the ORM filter, and Postgres FK checks
ignore RLS, so an unchecked id lets a row point at another org's user or project.
"""

import uuid
from functools import lru_cache
from typing import Any, Mapping, Optional

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from rhesis.backend.app.utils.uuid_utils import safe_uuid_convert

# Memo of ids already checked in this session, so bulk writes do not re-query.
_CHECKED_KEY = "_checked_foreign_refs"


class ForeignReferenceError(ValueError):
    """A foreign id in the payload is not usable by the caller (HTTP 400)."""

    def __init__(self, field: str):
        super().__init__(f"Invalid {field}: not found in your organization")
        self.field = field


@lru_cache(maxsize=None)
def _reference_columns(model: type) -> tuple[tuple[str, str], ...]:
    """(attribute key, target table) for each FK column on *model*."""
    refs = []
    for key, column in inspect(model).columns.items():
        for fk in getattr(column, "foreign_keys", ()):
            refs.append((key, fk.column.table.name))
    return tuple(refs)


def _row_in_org(db: Session, model: type, row_id: uuid.UUID, organization_id: str) -> bool:
    stmt = select(model.id).where(model.id == row_id, model.organization_id == organization_id)
    return db.execute(stmt).first() is not None


def _user_in_org(db: Session, user_id: uuid.UUID, organization_id: str) -> bool:
    from rhesis.backend.app.models.user import User

    return _row_in_org(db, User, user_id, organization_id)


def _may_use_project(
    db: Session, project_id: uuid.UUID, organization_id: str, user_id: Optional[str]
) -> bool:
    from rhesis.backend.app.auth.org_project_access import has_org_wide_project_access
    from rhesis.backend.app.models.project import Project
    from rhesis.backend.app.models.project_membership import ProjectMembership

    scope = db.info.get("_scope")
    if scope is not None and str(getattr(scope, "project_id", "") or "") == str(project_id):
        return True  # already validated by get_project_context
    if not _row_in_org(db, Project, project_id, organization_id):
        return False
    if not user_id:
        return True
    membership = select(ProjectMembership.id).where(
        ProjectMembership.project_id == project_id, ProjectMembership.user_id == user_id
    )
    if db.execute(membership).first() is not None:
        return True
    return has_org_wide_project_access(db, user_id, organization_id, acting=True)


def _is_valid(
    db: Session, table: str, row_id: uuid.UUID, organization_id: str, user_id: Optional[str]
) -> bool:
    if table == "user":
        return str(row_id) == str(user_id) or _user_in_org(db, row_id, organization_id)
    return _may_use_project(db, row_id, organization_id, user_id)


def validate_foreign_references(
    db: Session,
    model: type,
    data: Mapping[str, Any],
    organization_id: Optional[str],
    user_id: Optional[str] = None,
) -> None:
    """Raise ForeignReferenceError unless every user and project id in *data* is usable.

    A user reference must be a user of the caller's org; ``project_id`` must be a project
    the caller may use. Other FKs point at RLS-protected tables, so a foreign id there
    can be stored but is never read back.
    No-op without an organization (system and bootstrap paths).
    """
    if not organization_id:
        return
    organization_id = str(organization_id)
    checked = db.info.setdefault(_CHECKED_KEY, set())
    for key, table in _reference_columns(model):
        value = data.get(key)
        if value in (None, "") or table not in ("user", "project"):
            continue
        row_id = safe_uuid_convert(value)
        if row_id is None:
            raise ForeignReferenceError(key)
        memo = (table, row_id, organization_id, str(user_id))
        if memo in checked:
            continue
        if not _is_valid(db, table, row_id, organization_id, user_id):
            raise ForeignReferenceError(key)
        checked.add(memo)


def ensure_user_in_organization(
    db: Session, user_id: Any, organization_id: Any, field: str = "user_id"
) -> None:
    """Raise ForeignReferenceError unless *user_id* belongs to *organization_id*."""
    row_id = safe_uuid_convert(user_id)
    if row_id is None or not _user_in_org(db, row_id, str(organization_id)):
        raise ForeignReferenceError(field)

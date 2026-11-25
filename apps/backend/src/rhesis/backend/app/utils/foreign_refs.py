"""Check foreign ids in a write payload against the caller's organization.

Stamping only fills tenant columns that are missing; it never checks a supplied id.
The ``user`` table has no RLS and is skipped by the ORM filter, and Postgres FK checks
ignore RLS, so an unchecked id lets a row point at another org's user or project.
"""

import logging
import uuid
from functools import lru_cache
from typing import Any, Mapping, Optional

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from rhesis.backend.app.utils.uuid_utils import safe_uuid_convert

logger = logging.getLogger(__name__)

# Memo of ids already checked in this session, so bulk writes do not re-query.
_CHECKED_KEY = "_checked_foreign_refs"

# Org-wide reference catalogs. Their rows are seeded with project_id NULL, so they stay
# visible under every project scope and can be validated by a direct org-scoped read.
# Every other project_id-bearing table holds genuinely project-scoped rows that a caller
# may legitimately reference across their own projects; reading those under the current
# scope would false-reject such a reference, so they are left to the write-boundary FK
# guard in crud_utils instead. ``user`` and ``project`` keep their own handling below.
_ORG_CATALOG_TABLES = frozenset({"status", "type_lookup", "model"})
_VALIDATED_TABLES = frozenset({"user", "project"}) | _ORG_CATALOG_TABLES


class ForeignReferenceError(ValueError):
    """A foreign id in the payload is not usable by the caller (HTTP 400)."""

    def __init__(self, field: str, message: Optional[str] = None):
        super().__init__(message or f"Invalid {field}: not found in your organization")
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
    # Core select() skips the Query-based soft-delete filter, so exclude deleted rows here.
    stmt = select(model.id).where(
        model.id == row_id,
        model.organization_id == organization_id,
        model.deleted_at.is_(None),
    )
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
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == user_id,
        ProjectMembership.organization_id == organization_id,
        ProjectMembership.deleted_at.is_(None),
    )
    if db.execute(membership).first() is not None:
        return True
    return has_org_wide_project_access(db, user_id, organization_id, acting=True)


@lru_cache(maxsize=None)
def _model_for_table(table: str) -> Optional[type]:
    """The mapped model whose table is *table*, or None when nothing maps it."""
    from rhesis.backend.app.models.base import Base

    for mapper in Base.registry.mappers:
        if mapper.class_.__tablename__ == table:
            return mapper.class_
    return None


def _catalog_row_in_org(db: Session, table: str, row_id: uuid.UUID, organization_id: str) -> bool:
    from rhesis.backend.app.scope import bypass_tenant_filter

    model = _model_for_table(table)
    if model is None:
        # A catalog table with no mapped model means the table name drifted; surface it
        # so it is noticed. The write-boundary FK guard still backstops the reference.
        logger.warning("No model mapped for catalog table %r; skipping pre-write check", table)
        return True
    # bypass_tenant_filter drops the ORM auto-filter, but Postgres RLS stays in force: it,
    # together with the explicit organization_id predicate in _row_in_org, is the hard
    # boundary that keeps this read inside the caller's org.
    with bypass_tenant_filter():
        return _row_in_org(db, model, row_id, organization_id)


def _is_valid(
    db: Session, table: str, row_id: uuid.UUID, organization_id: str, user_id: Optional[str]
) -> bool:
    if table == "user":
        return str(row_id) == str(user_id) or _user_in_org(db, row_id, organization_id)
    if table == "project":
        return _may_use_project(db, row_id, organization_id, user_id)
    return _catalog_row_in_org(db, table, row_id, organization_id)


def validate_foreign_references(
    db: Session,
    model: type,
    data: Mapping[str, Any],
    organization_id: Optional[str],
    user_id: Optional[str] = None,
) -> None:
    """Raise ForeignReferenceError unless every checked id in *data* is usable.

    A user reference must be a user of the caller's org; ``project_id`` must be a project
    the caller may use; an org-wide catalog id (status, type lookup, model) must belong to
    the caller's org. Genuinely project-scoped FKs are not read here -- a bad id among them
    is caught at the write boundary instead (crud_utils), so a legitimate cross-project
    reference is never false-rejected.
    No-op without an organization (system and bootstrap paths).
    """
    if not organization_id:
        return
    organization_id = str(organization_id)
    checked = db.info.setdefault(_CHECKED_KEY, set())
    for key, table in _reference_columns(model):
        value = data.get(key)
        if value in (None, "") or table not in _VALIDATED_TABLES:
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


def field_from_integrity_error(error: Exception, model: type) -> Optional[str]:
    """The FK column a Postgres FK-violation refers to, read from its constraint name.

    Returns None when the column cannot be identified, so the caller can fall back to a
    generic field. Never echoes the database error itself.
    """
    orig = getattr(error, "orig", None)
    constraint = getattr(getattr(orig, "diag", None), "constraint_name", None) or ""
    haystack = f"{constraint} {orig}".lower()
    # Longest key first so e.g. ``test_set_id`` is not shadowed by ``test_id``.
    for key, _table in sorted(_reference_columns(model), key=lambda kt: -len(kt[0])):
        if key in haystack:
            return key
    return None

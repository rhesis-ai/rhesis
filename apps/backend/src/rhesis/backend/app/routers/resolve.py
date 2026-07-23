"""Cross-project entity resolution endpoint.

When a user follows a shared link to an entity that belongs to a different
project than their currently active one, the auto-filter (and Postgres RLS)
returns 404. This endpoint discovers which of the caller's *other* projects
contains the entity so the frontend can offer a "switch project" prompt
instead of a confusing "Not Found" page.

It probes each project the caller is a member of under that project's own
scope. Postgres ``FORCE ROW LEVEL SECURITY`` on project-scoped tables cannot
be bypassed from the non-privileged app role, so the ORM-level
``bypass_tenant_filter()`` is not sufficient on its own — probing under a real
project scope is the only cross-project lookup available to the app role.

Probing is sequential with early exit rather than parallel: each probe needs a
distinct ``app.current_project`` GUC, which is transaction-scoped, so parallel
probes would need separate connections (fanning out the small engine pool and
breaking the savepoint-isolated test harness) for no real gain — the lookups
are indexed primary-key hits on a rare, only-on-404 endpoint.
"""

import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import UnmappedClassError

from rhesis.backend.app import models
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.dependencies import get_project_context, get_tenant_db_session
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.user import User
from rhesis.backend.app.scope import bypass_tenant_filter

router = APIRouter(prefix="/resolve", tags=["resolve"])

# Entity tables with a protected detail page and cross-project link UX.
# Keep in sync with frontend ``parseEntityFromPathname`` / detail routes.
RESOLVABLE_ENTITY_TABLES = frozenset(
    {
        "behavior",
        "endpoint",
        "experiment",
        "metric",
        "source",
        "task",
        "test",
        "test_run",
        "test_set",
    }
)


@lru_cache(maxsize=1)
def get_resolvable_entities() -> dict[str, type]:
    """Return project-scoped models eligible for cross-project resolution.

    Restricted to ``RESOLVABLE_ENTITY_TABLES`` so internal tables are not
    exposed via guessed ``entity_type`` values. Model classes are resolved from
    SQLAlchemy's registry (same pattern as ``routers/recycle.py``).
    """
    entities: dict[str, type] = {}
    for mapper in Base.registry.mappers:
        try:
            model_class = mapper.class_
        except UnmappedClassError:
            continue
        table_name = model_class.__tablename__
        if table_name not in RESOLVABLE_ENTITY_TABLES:
            continue
        if hasattr(model_class, "project_id") and hasattr(model_class, "organization_id"):
            entities[table_name] = model_class
    return entities


class ResolvedEntity(BaseModel):
    resolution: str
    entity_type: str
    entity_id: str
    project_id: str | None = None
    project_name: str | None = None


def _entity_visible_in_project(
    db: Session,
    model_cls: type,
    entity_id: uuid.UUID,
    organization_id: str,
    user_id: str,
    project_id: str,
) -> bool:
    """Return True if the entity is visible (and not soft-deleted) with the
    session temporarily scoped to ``project_id``.

    ``temporary_project_scope`` sets ``app.current_project`` on the request
    connection and restores the caller's original scope on exit. Scoping to a
    real project is what makes the lookup correct under RLS: the row is only
    visible when ``app.current_project`` matches the entity's project.
    """
    with temporary_project_scope(db, organization_id, user_id, project_id):
        query = db.query(model_cls).filter(model_cls.id == entity_id)
        if hasattr(model_cls, "deleted_at"):
            query = query.filter(model_cls.deleted_at.is_(None))
        return query.first() is not None


@router.get("", response_model=ResolvedEntity)
def resolve_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    project_id: str | None = Depends(get_project_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Resolve an entity across the caller's *other* projects.

    Returns ``switchable`` with the target project when the entity lives in a
    project the caller is a member of; otherwise 404. Entities in projects the
    caller cannot access are indistinguishable from non-existent ones by
    design — the app role cannot see them under RLS, and not revealing their
    existence is the safer behavior.
    """
    model_cls = get_resolvable_entities().get(entity_type)
    if model_cls is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown entity type: {entity_type}",
        )

    organization_id = str(current_user.organization_id)
    user_id = str(current_user.id)
    active_project_id = project_id or ""

    # List the caller's projects (id + name) in one org-scoped query. Wrapped
    # in bypass_tenant_filter() because ProjectMembership carries a project_id
    # column, so the ORM auto-filter would otherwise pin the result to the
    # active project. Safe: project_membership has no DB-level project_isolation
    # policy and both tables keep tenant_isolation (org), so RLS still applies.
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
            )
            .all()
        )

    candidates = [(str(pid), name) for pid, name in rows if str(pid) != active_project_id]

    # Probe candidate projects one at a time, stopping at the first match. A
    # UUID PK is globally unique, so at most one project can contain the entity.
    for candidate_project_id, candidate_project_name in candidates:
        if _entity_visible_in_project(
            db, model_cls, entity_id, organization_id, user_id, candidate_project_id
        ):
            return ResolvedEntity(
                resolution="switchable",
                entity_type=entity_type,
                entity_id=str(entity_id),
                project_id=candidate_project_id,
                project_name=candidate_project_name,
            )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

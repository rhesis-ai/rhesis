"""Helpers for discovering a caller's project memberships.

Shared by any endpoint that needs to search across a caller's OTHER projects
under real RLS scope (project_isolation is FORCE-enabled and keyed on the
`app.current_project` GUC, so a lookup scoped to the active project cannot
see rows in a different one — see ``routers/resolve.py`` for the full
rationale). ``project_membership`` carries no ``project_isolation`` policy
(dropped intentionally in the ``b8c9d0e1f2a3`` migration), so it's queryable
at org scope; wrapped in ``bypass_tenant_filter()`` only because it *does*
have a ``project_id`` column that the ORM auto-filter would otherwise pin to
the active project.
"""

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.scope import bypass_tenant_filter


def list_other_member_projects(
    db: Session,
    organization_id: str,
    user_id: str,
    exclude_project_id: str | None = None,
) -> list[tuple[str, str]]:
    """Return (project_id, project_name) for every project the caller belongs
    to in this org, excluding ``exclude_project_id`` (typically the active one).
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
            )
            .all()
        )

    return [(str(pid), name) for pid, name in rows if str(pid) != (exclude_project_id or "")]

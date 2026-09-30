"""Walk every tenant scope a data migration needs to see.

``project_isolation`` is restrictive: with ``app.current_project`` blank, a role
without BYPASSRLS sees only rows whose ``project_id`` is NULL. Binding just the
org is therefore not enough to reach project rows, so bind each project in turn.
"""

from typing import Iterator, Optional, Tuple

import sqlalchemy as sa

_BIND = sa.text("""
    SELECT set_config('app.current_organization', :org_id, true),
           set_config('app.current_project', :project_id, true)
""")

# Readable with no org bound: the organization policy tolerates an unset GUC.
_ORGANIZATIONS = sa.text("SELECT id FROM organization WHERE deleted_at IS NULL")

# Soft-deleted projects are included: their rows are still there.
_PROJECTS = sa.text("SELECT id FROM project WHERE organization_id = CAST(:org_id AS uuid)")


def iter_tenant_scopes(conn) -> Iterator[Tuple[str, Optional[str]]]:
    """Yield ``(org_id, project_id)`` with the GUCs bound to that scope.

    Each org comes first with ``project_id`` None (its NULL-project rows), then
    once per project. Filter statements with
    ``project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)`` so a role that
    bypasses RLS does not process each org's rows once per scope.
    """
    org_ids = [str(row[0]) for row in conn.execute(_ORGANIZATIONS)]
    for org_id in org_ids:
        conn.execute(_BIND, {"org_id": org_id, "project_id": ""})
        project_ids = [str(row[0]) for row in conn.execute(_PROJECTS, {"org_id": org_id})]
        yield org_id, None
        for project_id in project_ids:
            conn.execute(_BIND, {"org_id": org_id, "project_id": project_id})
            yield org_id, project_id

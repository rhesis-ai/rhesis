"""Projects resource + shared local-project resolution used by endpoints."""

from __future__ import annotations

import uuid
from typing import Tuple

from rhesis.backend.app import models
from rhesis.backend.app.schemas.platform_sync import ResourceSyncResult
from rhesis.backend.app.services.organization import enroll_user_in_project
from rhesis.backend.app.utils.crud_utils import create_item

from ..registry import SyncContext, SyncResource, register


def resolve_local_project(
    ctx: SyncContext,
    name: str,
    description: str | None = None,
    icon: str | None = None,
    is_active: bool = True,
) -> Tuple[models.Project, bool]:
    """Return ``(project, created)`` for a local project by name, enrolling the user.

    Project names are resolved locally (their UUIDs differ prod↔local). The user is
    enrolled so synced endpoints are visible/selectable in the UI.
    """
    existing = ctx.db.query(models.Project).filter(models.Project.name == name).first()
    if existing:
        project, created = existing, False
    else:
        project = create_item(
            db=ctx.db,
            model=models.Project,
            item_data={
                "name": name,
                "description": description,
                "icon": icon,
                "is_active": is_active,
            },
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            commit=False,
        )
        created = True

    enroll_user_in_project(
        ctx.db,
        uuid.UUID(str(ctx.user_id)),
        project.id,
        uuid.UUID(str(ctx.organization_id)),
    )
    return project, created


def _fetch(ctx: SyncContext) -> list[dict]:
    prod_projects = ctx.cache.get("prod_projects")
    if prod_projects is None:
        from rhesis.sdk.clients.api import Endpoints

        prod_projects = ctx.client.list(Endpoints.PROJECTS)
        ctx.cache["prod_projects"] = prod_projects
    return prod_projects


def _upsert(ctx: SyncContext, records: list[dict]) -> ResourceSyncResult:
    result = ResourceSyncResult(resource="projects", label="Projects")
    for rec in records:
        name = rec.get("name")
        if not name:
            result.skipped += 1
            continue
        _project, created = resolve_local_project(
            ctx,
            name,
            description=rec.get("description"),
            icon=rec.get("icon"),
            is_active=rec.get("is_active", True),
        )
        if created:
            result.created += 1
        else:
            result.skipped += 1
    return result


register(
    SyncResource(
        key="projects",
        label="Projects",
        fetch=_fetch,
        upsert=_upsert,
        description="Projects (also pulled automatically when syncing endpoints).",
    )
)

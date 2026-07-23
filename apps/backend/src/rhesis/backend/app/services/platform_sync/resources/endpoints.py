"""Endpoints resource — config only; auth secrets are reported as gaps."""

from __future__ import annotations

from collections import defaultdict

from rhesis.backend.app import models, schemas
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.schemas.platform_sync import ResourceSyncResult, SyncGap
from rhesis.backend.app.utils.crud_utils import create_item, get_or_create_status
from rhesis.sdk.clients.api import Endpoints

from ..registry import SyncContext, SyncResource, register
from .projects import resolve_local_project

_LABEL = "Endpoints"


def _fetch(ctx: SyncContext) -> list[dict]:
    """Fetch endpoints across every accessible project.

    ``Endpoint.project_id`` is NOT NULL, so a token that is not project-scoped
    sees only ``project_id IS NULL`` rows. We enumerate per prod project (plus the
    unscoped default) and dedupe by id. A project we cannot read is skipped rather
    than aborting the whole fetch.
    """
    prod_projects = ctx.cache.get("prod_projects")
    if prod_projects is None:
        prod_projects = ctx.client.list(Endpoints.PROJECTS)
        ctx.cache["prod_projects"] = prod_projects

    seen: set = set()
    out: list[dict] = []
    project_ids = [None] + [p.get("id") for p in prod_projects if p.get("id")]
    for project_id in project_ids:
        if project_id is None:
            ctx.client.clear_project()
        else:
            ctx.client.set_project(project_id)
        try:
            batch = ctx.client.list(Endpoints.ENDPOINTS)
        except Exception:
            continue
        for endpoint in batch:
            endpoint_id = endpoint.get("id")
            if endpoint_id not in seen:
                seen.add(endpoint_id)
                out.append(endpoint)
    ctx.client.clear_project()
    return out


def _record_gaps(result: ResourceSyncResult, rec: dict) -> None:
    name = rec.get("name")
    if rec.get("has_auth_token"):
        result.gaps.append(
            SyncGap(
                resource="endpoints",
                name=name,
                field="auth_token",
                reason="Bearer tokens are never returned by the platform — left blank.",
            )
        )
    if rec.get("auth_type") == "client_credentials" or (
        rec.get("client_id") and rec.get("token_url")
    ):
        result.gaps.append(
            SyncGap(
                resource="endpoints",
                name=name,
                field="client_secret",
                reason="OAuth client secrets are never returned by the platform — left blank.",
            )
        )


def _upsert(ctx: SyncContext, records: list[dict]) -> ResourceSyncResult:
    result = ResourceSyncResult(resource="endpoints", label=_LABEL)

    by_project: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        project_name = (rec.get("project") or {}).get("name") or "Default"
        by_project[project_name].append(rec)

    for project_name, recs in by_project.items():
        project, _ = resolve_local_project(ctx, project_name)
        # Bind project scope so idempotency lookups match and auto-stamp/RLS see the
        # right project_id for the NOT-NULL column (see backend AGENTS.md).
        with temporary_project_scope(ctx.db, ctx.organization_id, ctx.user_id, str(project.id)):
            for rec in recs:
                name = rec.get("name")
                if not name:
                    result.skipped += 1
                    continue

                existing = (
                    ctx.db.query(models.Endpoint).filter(models.Endpoint.name == name).first()
                )
                if existing:
                    result.skipped += 1
                    _record_gaps(result, rec)
                    continue

                status_obj = get_or_create_status(
                    db=ctx.db,
                    name=(rec.get("status") or {}).get("name") or "Active",
                    entity_type=EntityType.GENERAL,
                    organization_id=ctx.organization_id,
                    user_id=ctx.user_id,
                    commit=False,
                )

                payload = schemas.EndpointCreate(
                    name=name,
                    description=rec.get("description"),
                    connection_type=rec.get("connection_type") or "REST",
                    url=rec.get("url"),
                    auth=rec.get("auth"),
                    environment=rec.get("environment") or "development",
                    config_source=rec.get("config_source") or "manual",
                    openapi_spec_url=rec.get("openapi_spec_url"),
                    openapi_spec=rec.get("openapi_spec"),
                    llm_suggestions=rec.get("llm_suggestions"),
                    endpoint_metadata=rec.get("endpoint_metadata"),
                    method=rec.get("method"),
                    endpoint_path=rec.get("endpoint_path"),
                    request_headers=rec.get("request_headers"),
                    query_params=rec.get("query_params"),
                    request_mapping=rec.get("request_mapping"),
                    input_mappings=rec.get("input_mappings"),
                    response_format=rec.get("response_format") or "json",
                    response_mapping=rec.get("response_mapping"),
                    validation_rules=rec.get("validation_rules"),
                    disable_tracing=rec.get("disable_tracing", False),
                    auth_type=rec.get("auth_type"),
                    auth_token=None,  # secret never returned by the platform
                    client_secret=None,  # secret never returned by the platform
                    client_id=rec.get("client_id"),
                    token_url=rec.get("token_url"),
                    scopes=rec.get("scopes"),
                    audience=rec.get("audience"),
                    extra_payload=rec.get("extra_payload"),
                    status_id=status_obj.id if status_obj else None,
                    project_id=project.id,
                )
                create_item(
                    db=ctx.db,
                    model=models.Endpoint,
                    item_data=payload,
                    organization_id=ctx.organization_id,
                    user_id=ctx.user_id,
                    commit=False,
                )
                result.created += 1
                _record_gaps(result, rec)
    return result


register(
    SyncResource(
        key="endpoints",
        label=_LABEL,
        fetch=_fetch,
        upsert=_upsert,
        dependencies=("projects",),
        description="Target endpoints. Auth secrets are left blank and reported as gaps.",
    )
)

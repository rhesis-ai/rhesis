"""Simple name-based resources: behaviors, topics, categories.

Each is a self-contained lookup entity synced by name via an existing
``get_or_create_*`` helper. Adding another such resource is a one-line
``register(...)`` below.
"""

from __future__ import annotations

from typing import Callable

from rhesis.backend.app import models
from rhesis.backend.app.schemas.platform_sync import ResourceSyncResult
from rhesis.backend.app.utils.crud_utils import (
    get_or_create_behavior,
    get_or_create_category,
    get_or_create_topic,
)
from rhesis.sdk.clients.api import Endpoints

from ..registry import SyncContext, SyncResource, register

CreatorFn = Callable[[SyncContext, dict, str], None]


def _make_resource(
    key: str,
    label: str,
    endpoint: Endpoints,
    model_cls: type,
    creator: CreatorFn,
    description: str,
) -> SyncResource:
    def _fetch(ctx: SyncContext) -> list[dict]:
        return ctx.client.list(endpoint)

    def _upsert(ctx: SyncContext, records: list[dict]) -> ResourceSyncResult:
        result = ResourceSyncResult(resource=key, label=label)
        for rec in records:
            name = rec.get("name")
            if not name:
                result.skipped += 1
                continue
            existing = ctx.db.query(model_cls).filter(model_cls.name == name).first()
            if existing:
                result.skipped += 1
                continue
            creator(ctx, rec, name)
            result.created += 1
        return result

    return SyncResource(
        key=key,
        label=label,
        fetch=_fetch,
        upsert=_upsert,
        description=description,
    )


def _create_behavior(ctx: SyncContext, rec: dict, name: str) -> None:
    get_or_create_behavior(
        ctx.db,
        name=name,
        description=rec.get("description"),
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        commit=False,
    )


def _create_topic(ctx: SyncContext, rec: dict, name: str) -> None:
    get_or_create_topic(
        ctx.db,
        name=name,
        description=rec.get("description"),
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        commit=False,
    )


def _create_category(ctx: SyncContext, rec: dict, name: str) -> None:
    get_or_create_category(
        ctx.db,
        name=name,
        description=rec.get("description"),
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        commit=False,
    )


register(
    _make_resource(
        "behaviors",
        "Behaviors",
        Endpoints.BEHAVIORS,
        models.Behavior,
        _create_behavior,
        "Evaluation behaviors.",
    )
)
register(
    _make_resource(
        "topics",
        "Topics",
        Endpoints.TOPICS,
        models.Topic,
        _create_topic,
        "Topics.",
    )
)
register(
    _make_resource(
        "categories",
        "Categories",
        Endpoints.CATEGORIES,
        models.Category,
        _create_category,
        "Categories.",
    )
)

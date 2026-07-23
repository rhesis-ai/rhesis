"""Models resource — includes the default (rhesis) and Polyphemus system models.

System-provider models (rhesis/polyphemus) authenticate against Rhesis-hosted
services with a Rhesis platform key. The platform never returns a stored key, but
the caller *pasted* a valid key to run the sync — so for these providers we store
that pasted key on the synced model, making it usable locally without touching the
backend's ``RHESIS_API_KEY`` env var. They are added as NEW rows under a
provenance-tagged name (``… (synced from <host>)``) so they neither collide with
nor overwrite any existing keyless default, and re-syncing from the same platform
skips them.

Other providers (openai, anthropic, …) need their own provider key, which the
platform never returns, so those are synced with a blank key and reported as gaps.
"""

from __future__ import annotations

import uuid
from urllib.parse import urlparse

from rhesis.backend.app import models
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.schemas.platform_sync import ResourceSyncResult, SyncGap
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    get_or_create_status,
    get_or_create_type_lookup,
)
from rhesis.sdk.clients.api import Endpoints

from ..registry import SyncContext, SyncResource, register

# Providers that authenticate with a Rhesis platform key (so the pasted key is
# stored on them and makes them immediately usable locally).
_SYSTEM_PROVIDERS = {"rhesis", "polyphemus"}
_LABEL = "Models"


def _platform_host(ctx: SyncContext) -> str:
    return urlparse(ctx.client.base_url).netloc or ctx.client.base_url


def _upsert(ctx: SyncContext, records: list[dict]) -> ResourceSyncResult:
    result = ResourceSyncResult(resource="models", label=_LABEL)
    host = _platform_host(ctx)

    for rec in records:
        name = rec.get("name")
        if not name:
            result.skipped += 1
            continue

        provider_value = (rec.get("provider_type") or {}).get("type_value")
        is_system = provider_value in _SYSTEM_PROVIDERS

        # System models are added as a distinct, provenance-tagged row carrying the
        # pasted key; other providers keep their original name and a blank key.
        target_name = f"{name} (synced from {host})" if is_system else name
        key_value = ctx.api_key if is_system else ""

        existing = ctx.db.query(models.Model).filter(models.Model.name == target_name).first()
        if existing:
            result.skipped += 1
            if not is_system:
                _record_key_gap(result, target_name, provider_value)
            continue

        provider_type = None
        if provider_value:
            provider_type = get_or_create_type_lookup(
                db=ctx.db,
                type_name="ProviderType",
                type_value=provider_value,
                organization_id=ctx.organization_id,
                user_id=ctx.user_id,
                commit=False,
            )
        status_obj = get_or_create_status(
            db=ctx.db,
            name=(rec.get("status") or {}).get("name") or "Available",
            entity_type=EntityType.MODEL,
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            commit=False,
        )

        create_item(
            db=ctx.db,
            model=models.Model,
            item_data={
                "name": target_name,
                "description": rec.get("description"),
                "icon": rec.get("icon") or (provider_value if is_system else None),
                "model_name": rec.get("model_name") or "default",
                "model_type": rec.get("model_type") or "language",
                "endpoint": rec.get("endpoint"),
                "request_headers": rec.get("request_headers"),
                "key": key_value or "",
                "is_protected": False,
                "provider_type_id": provider_type.id if provider_type else None,
                "status_id": status_obj.id if status_obj else None,
                "owner_id": uuid.UUID(str(ctx.user_id)),
            },
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            commit=False,
        )
        result.created += 1
        if not is_system:
            _record_key_gap(result, target_name, provider_value)
    return result


def _record_key_gap(result: ResourceSyncResult, name: str, provider_value: str | None) -> None:
    result.gaps.append(
        SyncGap(
            resource="models",
            name=name,
            field="key",
            reason=(
                f"'{provider_value}' provider API keys are never returned by the platform "
                "— left blank."
            ),
        )
    )


def _fetch(ctx: SyncContext) -> list[dict]:
    return ctx.client.list(Endpoints.MODELS)


register(
    SyncResource(
        key="models",
        label=_LABEL,
        fetch=_fetch,
        upsert=_upsert,
        description=(
            "LLM models. The default and Polyphemus models are added with your pasted "
            "platform key so they work locally; other providers need their own key."
        ),
    )
)

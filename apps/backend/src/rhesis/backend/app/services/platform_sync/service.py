"""Orchestration for a single platform-sync run."""

from __future__ import annotations

import logging
from typing import List

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.schemas.platform_sync import (
    PlatformSyncSummary,
    ResourceSyncResult,
)

from .client import PlatformClient
from .registry import REGISTRY, SyncContext, resolve_order

logger = logging.getLogger(__name__)


def run_platform_sync(
    *,
    db: Session,
    organization_id: str,
    user_id: str,
    api_key: str,
    base_url: str,
    selected: List[str],
) -> PlatformSyncSummary:
    """Pull the selected resources from the platform and upsert them locally.

    Each resource is fetched, upserted, and committed independently so a failure in
    one resource records an error without corrupting the others.
    """
    client = PlatformClient(api_key=api_key, base_url=base_url)

    try:
        info = client.introspect_token()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else None
        if code in (401, 403):
            raise HTTPException(status_code=401, detail="The platform API key was rejected.")
        raise HTTPException(status_code=502, detail="Could not reach the Rhesis platform.")
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach the Rhesis platform.")

    ctx = SyncContext(
        db=db,
        organization_id=organization_id,
        user_id=user_id,
        client=client,
        api_key=api_key,
    )
    summary = PlatformSyncSummary(
        base_url=client.base_url,
        source_organization_id=info.get("organization_id"),
        source_user_email=info.get("user_email"),
    )

    # resolve_order raises 422 for an unknown key before any work is done.
    for key in resolve_order(selected):
        resource = REGISTRY[key]
        try:
            records = resource.fetch(ctx)
            result = resource.upsert(ctx, records)
            db.commit()
        except Exception as exc:  # noqa: BLE001 — isolate per-resource failures
            db.rollback()
            logger.exception("platform-sync: resource '%s' failed", key)
            result = ResourceSyncResult(resource=key, label=resource.label, errors=[str(exc)])
        summary.results.append(result)
        summary.gaps.extend(result.gaps)

    return summary

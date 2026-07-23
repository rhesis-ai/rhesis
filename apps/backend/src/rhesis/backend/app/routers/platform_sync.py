"""Local-only router for syncing platform resources into a local deployment."""

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.local_only import require_local_deployment
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.schemas.platform_sync import (
    PlatformSyncRequest,
    PlatformSyncSummary,
    ResourceDescriptorOut,
)
from rhesis.backend.app.services.platform_sync import REGISTRY, run_platform_sync

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/platform-sync",
    tags=["platform-sync"],
    dependencies=[Depends(require_current_user_or_token), Depends(require_local_deployment)],
    responses={404: {"description": "Not found"}},
)


@router.get("/resources", response_model=List[ResourceDescriptorOut])
def list_sync_resources():
    """List the resource types that can be synced (drives the checkbox UI)."""
    return [
        ResourceDescriptorOut(
            key=resource.key,
            label=resource.label,
            dependencies=list(resource.dependencies),
            description=resource.description,
        )
        for resource in REGISTRY.values()
    ]


@router.post("", response_model=PlatformSyncSummary)
def platform_sync(
    payload: PlatformSyncRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """Pull the selected resources from the platform into the local database."""
    organization_id, user_id = tenant_context
    return run_platform_sync(
        db=db,
        organization_id=organization_id,
        user_id=user_id,
        api_key=payload.api_key,
        base_url=payload.base_url,
        selected=payload.resources,
    )

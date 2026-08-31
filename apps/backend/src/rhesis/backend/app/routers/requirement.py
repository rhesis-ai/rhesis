import logging
import uuid
from typing import List

from fastapi import Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import create_model
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import (
    REQUIREMENT_RESOURCE_NAME,
    REQUIREMENT_ROUTE_PREFIX,
    REQUIREMENT_TAG,
)
from rhesis.backend.app.crud import requirement as requirement_crud
from rhesis.backend.app.crud.metric import (
    add_requirement_to_metric,
    get_requirement_metrics,
    remove_requirement_from_metric,
)
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.tag import TagRead
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.odata import apply_select

logger = logging.getLogger(__name__)

# Requirement's associated metrics only need Metric's own fields (name, description,
# backend_type, metric_type, score_type, metric_scope) -- confirmed against actual
# frontend usage (RequirementCard/RequirementsClient/RequirementMetricsViewer/RequirementDetailTabs,
# and the standalone GET /requirements/{id}/metrics/ compare-page caller). None of
# MetricDetail's relationship fields (status/assignee/owner/model/requirements/
# test_sets/organization/project) are read here, so this stays on the base
# Metric schema rather than sharing MetricDetail with routers/metric.py.
# tags is overridden to TagRead (not the base Tag) to match the minimal shape
# used everywhere else tags are embedded in a read response (e.g. RequirementDetail,
# TestSetDetail) -- otherwise this endpoint alone leaks organization_id/user_id
# per tag.
RequirementWithMetricsSchema = create_model(
    "RequirementWithMetrics",
    __base__=schemas.Requirement,
    metrics=(List[schemas.Metric], []),
    tags=(List[TagRead], []),
)

router = RhesisRouter(
    prefix=REQUIREMENT_ROUTE_PREFIX,
    tags=[REQUIREMENT_TAG],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource=REQUIREMENT_RESOURCE_NAME,
)


@router.post("/", response_model=RequirementWithMetricsSchema)
@handle_database_exceptions(
    entity_name=REQUIREMENT_RESOURCE_NAME,
    custom_unique_message="Requirement with this name already exists",
)
def create_requirement(
    requirement: schemas.RequirementCreate,
    db: Session = Depends(
        get_tenant_db_session
    ),  # ← Uses drop-in replacement with automatic session variables
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create requirement with automatic session variables for RLS."""
    organization_id, user_id = tenant_context

    return requirement_crud.create_requirement(
        db=db, requirement=requirement, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[RequirementWithMetricsSchema])
@with_count_header(model=models.Requirement)
def read_requirements(
    response: Response,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    select: str | None = Query(
        None,
        alias="$select",
        description="Comma-separated list of fields to return",
    ),
    db: Session = Depends(get_tenant_db_session),  # ← Uses drop-in replacement
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all requirements with automatic session variables for RLS."""
    organization_id, user_id = tenant_context

    results = requirement_crud.get_requirements_detail(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    if select:
        serialized = jsonable_encoder(results)
        return JSONResponse(content=apply_select(serialized, select))
    return results


@router.get("/{requirement_id}", response_model=RequirementWithMetricsSchema)
def read_requirement(
    requirement_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get requirement by ID with automatic session variables for RLS."""
    organization_id, user_id = tenant_context
    db_requirement = requirement_crud.get_requirement(
        db, requirement_id=requirement_id, organization_id=organization_id, user_id=user_id
    )
    if db_requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return db_requirement


@router.delete("/{requirement_id}")
def delete_requirement(
    requirement_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete requirement with automatic session variables for RLS."""
    organization_id, user_id = tenant_context
    db_requirement = requirement_crud.delete_requirement(
        db, requirement_id=requirement_id, organization_id=organization_id, user_id=user_id
    )
    if db_requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return db_requirement


@router.put("/{requirement_id}", response_model=RequirementWithMetricsSchema)
@handle_database_exceptions(
    entity_name=REQUIREMENT_RESOURCE_NAME,
    custom_unique_message="Requirement with this name already exists",
)
def update_requirement(
    requirement_id: uuid.UUID,
    requirement: schemas.RequirementUpdate,
    db: Session = Depends(get_tenant_db_session),  # ← Uses drop-in replacement
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update requirement with automatic session variables for RLS."""
    organization_id, user_id = tenant_context
    db_requirement = requirement_crud.update_requirement(
        db,
        requirement_id=requirement_id,
        requirement=requirement,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return db_requirement


@router.get("/{requirement_id}/metrics/", response_model=List[schemas.Metric])
@with_count_header(model=models.Metric)
def read_requirement_metrics(
    response: Response,
    requirement_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
    organization_id: str | None = None,  # For with_count_header decorator
    user_id: str | None = None,  # For with_count_header decorator
):
    """Get all metrics associated with a requirement"""
    try:
        organization_id, user_id = tenant_context  # SECURITY: Get tenant context
        metrics = get_requirement_metrics(
            db,
            requirement_id=requirement_id,
            organization_id=organization_id,  # SECURITY: Pass organization_id for filtering
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )
        return metrics
    except ValueError as e:
        logger.error(f"Error getting requirement metrics: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{requirement_id}/metrics/{metric_id}")
def add_metric_to_requirement(
    requirement_id: uuid.UUID,
    metric_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Add a metric to a requirement"""
    try:
        added = add_requirement_to_metric(
            db=db,
            metric_id=metric_id,
            requirement_id=requirement_id,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
        )
        if added:
            return {"status": "success", "message": "Metric added to requirement"}
        return {"status": "success", "message": "Metric was already associated with requirement"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{requirement_id}/metrics/{metric_id}")
def remove_metric_from_requirement(
    requirement_id: uuid.UUID,
    metric_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Remove a metric from a requirement"""
    try:
        removed = remove_requirement_from_metric(
            db=db,
            metric_id=metric_id,
            requirement_id=requirement_id,
            organization_id=current_user.organization_id,
        )
        if removed:
            return {"status": "success", "message": "Metric removed from requirement"}
        raise HTTPException(status_code=404, detail="Metric was not associated with requirement")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

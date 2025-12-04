import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import create_model
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.metric import MetricDetail as MetricDetailSchema
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header

logger = logging.getLogger(__name__)

# Create behavior schema with full metric details (includes score_type and metric_scope)
BehaviorWithMetricsSchema = create_model(
    "BehaviorWithMetrics",
    __base__=schemas.Behavior,
    metrics=(List[MetricDetailSchema], []),
)

router = APIRouter(
    prefix="/behaviors",
    tags=["behaviors"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=BehaviorWithMetricsSchema)
@handle_database_exceptions(
    entity_name="behavior", custom_unique_message="Behavior with this name already exists"
)
def create_behavior(
    behavior: schemas.BehaviorCreate,
    db: Session = Depends(
        get_tenant_db_session
    ),  # ← Uses drop-in replacement with automatic session variables
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create behavior with automatic session variables for RLS."""
    organization_id, user_id = tenant_context

    return crud.create_behavior(
        db=db, behavior=behavior, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=List[BehaviorWithMetricsSchema])
@with_count_header(model=models.Behavior)
def read_behaviors(
    response: Response,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),  # ← Uses drop-in replacement
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all behaviors with automatic session variables for RLS."""
    organization_id, user_id = tenant_context

    return crud.get_items_detail(
        db=db,
        model=models.Behavior,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        nested_relationships={"metrics": ["metric_type", "backend_type"]},
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{behavior_id}")
def read_behavior(
    behavior_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get behavior by ID with automatic session variables for RLS."""
    organization_id, user_id = tenant_context
    db_behavior = crud.get_behavior(
        db, behavior_id=behavior_id, organization_id=organization_id, user_id=user_id
    )
    if db_behavior is None:
        raise HTTPException(status_code=404, detail="Behavior not found")
    return db_behavior


@router.delete("/{behavior_id}")
def delete_behavior(
    behavior_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete behavior with automatic session variables for RLS."""
    organization_id, user_id = tenant_context
    db_behavior = crud.delete_behavior(
        db, behavior_id=behavior_id, organization_id=organization_id, user_id=user_id
    )
    if db_behavior is None:
        raise HTTPException(status_code=404, detail="Behavior not found")
    return db_behavior


@router.put("/{behavior_id}", response_model=BehaviorWithMetricsSchema)
@handle_database_exceptions(
    entity_name="behavior", custom_unique_message="Behavior with this name already exists"
)
def update_behavior(
    behavior_id: uuid.UUID,
    behavior: schemas.BehaviorUpdate,
    db: Session = Depends(get_tenant_db_session),  # ← Uses drop-in replacement
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update behavior with automatic session variables for RLS."""
    organization_id, user_id = tenant_context
    db_behavior = crud.update_behavior(
        db,
        behavior_id=behavior_id,
        behavior=behavior,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_behavior is None:
        raise HTTPException(status_code=404, detail="Behavior not found")
    return db_behavior


@router.get("/{behavior_id}/metrics/", response_model=List[MetricDetailSchema])
@with_count_header(model=models.Metric)
def read_behavior_metrics(
    response: Response,
    behavior_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
    organization_id: str = None,  # For with_count_header decorator
    user_id: str = None,  # For with_count_header decorator
):
    """Get all metrics associated with a behavior"""
    try:
        organization_id, user_id = tenant_context  # SECURITY: Get tenant context
        metrics = crud.get_behavior_metrics(
            db,
            behavior_id=behavior_id,
            organization_id=organization_id,  # SECURITY: Pass organization_id for filtering
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )
        return metrics
    except ValueError as e:
        logger.error(f"Error getting behavior metrics: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{behavior_id}/metrics/{metric_id}")
def add_metric_to_behavior(
    behavior_id: uuid.UUID,
    metric_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Add a metric to a behavior"""
    try:
        added = crud.add_behavior_to_metric(
            db=db,
            metric_id=metric_id,
            behavior_id=behavior_id,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
        )
        if added:
            return {"status": "success", "message": "Metric added to behavior"}
        return {"status": "success", "message": "Metric was already associated with behavior"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{behavior_id}/metrics/{metric_id}")
def remove_metric_from_behavior(
    behavior_id: uuid.UUID,
    metric_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Remove a metric from a behavior"""
    try:
        removed = crud.remove_behavior_from_metric(
            db=db,
            metric_id=metric_id,
            behavior_id=behavior_id,
            organization_id=current_user.organization_id,
        )
        if removed:
            return {"status": "success", "message": "Metric removed from behavior"}
        raise HTTPException(status_code=404, detail="Metric was not associated with behavior")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Metric with many-to-many relationships included
MetricDetailSchema = create_detailed_schema(
    schemas.Metric, models.Metric, include_many_to_many=True
)
BehaviorDetailSchema = create_detailed_schema(schemas.Behavior, models.Behavior)

router = APIRouter(
    prefix="/metrics", tags=["metrics"], responses={404: {"description": "Not found"}}
)


@router.post("/", response_model=schemas.Metric)
@handle_database_exceptions(
    entity_name="metric", custom_unique_message="Metric with this name already exists"
)
def create_metric(
    metric: schemas.MetricCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create metric with super optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    from rhesis.backend.logging import logger
    
    organization_id, user_id = tenant_context

    logger.info(f"Received metric creation request: {metric.name} from user: {current_user.id}")
    logger.debug(f"Metric data: backend_type={getattr(metric, 'backend_type', None)}, "
                f"metric_type={getattr(metric, 'metric_type', None)}")

    try:
    # Set the current user as the owner if not specified
    if not metric.owner_id:
        metric.owner_id = current_user.id

        result = crud.create_metric(
        db=db, metric=metric, organization_id=organization_id, user_id=user_id
    )
        
        logger.info(f"Successfully created metric '{metric.name}' with ID: {result.id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in metric creation endpoint for '{metric.name}': {e}", exc_info=True)
        raise


@router.get("/", response_model=List[MetricDetailSchema])
@with_count_header(model=models.Metric)
def read_metrics(
    response: Response,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all metrics with their related objects"""
    organization_id, user_id = tenant_context
    metrics = crud.get_metrics(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    return metrics


@router.get("/{metric_id}", response_model=MetricDetailSchema)
def read_metric(
    metric_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific metric by ID with its related objects"""
    organization_id, user_id = tenant_context
    # Use get_item_detail which properly handles soft-deleted items (raises ItemDeletedException)
    from rhesis.backend.app.utils.crud_utils import get_item_detail

    db_metric = get_item_detail(db, models.Metric, metric_id, organization_id, user_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    return db_metric


@router.put("/{metric_id}", response_model=schemas.Metric)
@handle_database_exceptions(
    entity_name="metric", custom_unique_message="Metric with this name already exists"
)
def update_metric(
    metric_id: UUID,
    metric: schemas.MetricUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update a metric"""
    organization_id, user_id = tenant_context
    db_metric = crud.get_metric(db, metric_id=metric_id, organization_id=organization_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")

    # Check if the user has permission to update this metric
    if db_metric.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this metric")

    return crud.update_metric(
        db=db, metric_id=metric_id, metric=metric, organization_id=organization_id, user_id=user_id
    )


@router.delete("/{metric_id}", response_model=schemas.Metric)
def delete_metric(
    metric_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a metric"""
    organization_id, user_id = tenant_context
    db_metric = crud.get_metric(db, metric_id=metric_id, organization_id=organization_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")

    # Check if the user has permission to delete this metric
    if db_metric.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete this metric")

    return crud.delete_metric(
        db=db, metric_id=metric_id, organization_id=organization_id, user_id=user_id
    )


@router.post("/{metric_id}/behaviors/{behavior_id}")
def add_behavior_to_metric(
    metric_id: UUID,
    behavior_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Add a behavior to a metric"""
    organization_id, user_id = tenant_context
    # Check if the metric exists and user has permission
    db_metric = crud.get_metric(db, metric_id=metric_id, organization_id=organization_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")

    if db_metric.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to modify this metric")

    try:
        added = crud.add_behavior_to_metric(
            db=db,
            metric_id=metric_id,
            behavior_id=behavior_id,
            user_id=current_user.id,
            organization_id=organization_id,
        )
        if added:
            return {"status": "success", "message": "Behavior added to metric"}
        return {"status": "success", "message": "Behavior was already associated with metric"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{metric_id}/behaviors/{behavior_id}")
def remove_behavior_from_metric(
    metric_id: UUID,
    behavior_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Remove a behavior from a metric"""
    organization_id, user_id = tenant_context
    # Check if the metric exists and user has permission
    db_metric = crud.get_metric(db, metric_id=metric_id, organization_id=organization_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")

    if db_metric.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to modify this metric")

    try:
        removed = crud.remove_behavior_from_metric(
            db=db, metric_id=metric_id, behavior_id=behavior_id, organization_id=organization_id
        )
        if removed:
            return {"status": "success", "message": "Behavior removed from metric"}
        return {"status": "success", "message": "Behavior was not associated with metric"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{metric_id}/behaviors/", response_model=List[BehaviorDetailSchema])
@with_count_header(model=models.Behavior)
def read_metric_behaviors(
    response: Response,
    metric_id: UUID,
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
    """Get all behaviors associated with a metric"""
    try:
        organization_id, user_id = tenant_context  # SECURITY: Get tenant context
        behaviors = crud.get_metric_behaviors(
            db,
            metric_id=metric_id,
            organization_id=organization_id,  # SECURITY: Pass organization_id for filtering
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )
        return behaviors
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

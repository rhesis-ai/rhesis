from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Metric
MetricDetailSchema = create_detailed_schema(schemas.Metric, models.Metric)
BehaviorDetailSchema = create_detailed_schema(schemas.Behavior, models.Behavior)

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.Metric)
def create_metric(
    metric: schemas.MetricCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Create a new metric"""
    # Set the owner to the current user if not provided
    if not metric.owner_id:
        metric.owner_id = current_user.id
    return crud.create_metric(db=db, metric=metric)


@router.get("/", response_model=List[MetricDetailSchema])
@with_count_header(model=models.Metric)
def read_metrics(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get all metrics with their related objects"""
    metrics = crud.get_metrics(
        db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )
    return metrics


@router.get("/{metric_id}", response_model=MetricDetailSchema)
def read_metric(
    metric_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get a specific metric by ID with its related objects"""
    db_metric = crud.get_metric(db, metric_id=metric_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    return db_metric


@router.put("/{metric_id}", response_model=schemas.Metric)
def update_metric(
    metric_id: UUID,
    metric: schemas.MetricUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Update a metric"""
    db_metric = crud.get_metric(db, metric_id=metric_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")

    # Check if the user has permission to update this metric
    if db_metric.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this metric")

    return crud.update_metric(db=db, metric_id=metric_id, metric=metric)


@router.delete("/{metric_id}", response_model=schemas.Metric)
def delete_metric(
    metric_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Delete a metric"""
    db_metric = crud.get_metric(db, metric_id=metric_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")

    # Check if the user has permission to delete this metric
    if db_metric.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete this metric")

    return crud.delete_metric(db=db, metric_id=metric_id)


@router.post("/{metric_id}/behaviors/{behavior_id}")
def add_behavior_to_metric(
    metric_id: UUID,
    behavior_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Add a behavior to a metric"""
    # Check if the metric exists and user has permission
    db_metric = crud.get_metric(db, metric_id=metric_id)
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
            organization_id=current_user.organization_id,
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
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Remove a behavior from a metric"""
    # Check if the metric exists and user has permission
    db_metric = crud.get_metric(db, metric_id=metric_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    if db_metric.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to modify this metric")

    try:
        removed = crud.remove_behavior_from_metric(
            db=db,
            metric_id=metric_id,
            behavior_id=behavior_id,
            organization_id=current_user.organization_id,
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
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get all behaviors associated with a metric"""
    try:
        behaviors = crud.get_metric_behaviors(
            db,
            metric_id=metric_id,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )
        return behaviors
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

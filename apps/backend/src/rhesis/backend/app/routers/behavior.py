import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema with metrics support and nested relationships
BehaviorWithMetricsSchema = create_detailed_schema(
    schemas.Behavior, 
    models.Behavior, 
    include_many_to_many=True,
    include_nested_relationships={
        "metrics": ["metric_type", "backend_type"]
    }
)
MetricDetailSchema = create_detailed_schema(schemas.Metric, models.Metric)

router = APIRouter(
    prefix="/behaviors",
    tags=["behaviors"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=BehaviorWithMetricsSchema)
def create_behavior(
    behavior: schemas.BehaviorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        return crud.create_behavior(db=db, behavior=behavior)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations (like foreign key constraints)
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            if "status_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid status reference")
            raise HTTPException(status_code=400, detail="Invalid reference in behavior data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Behavior with this name already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[BehaviorWithMetricsSchema])
@with_count_header(model=models.Behavior)
def read_behaviors(
    response: Response,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all behaviors with all related objects loaded using get_items_detail"""
    
    print(f"🔍 [DEBUG] Behaviors endpoint called with params: skip={skip}, limit={limit}, sort_by={sort_by}, sort_order={sort_order}, filter={filter}")
    print(f"🔍 [DEBUG] Current user: {current_user.id if current_user else None}, org: {current_user.organization_id if current_user else None}")

    try:
        print(f"🔍 [DEBUG] Using optimized relationship loading...")
        # Use get_items_detail with optimized loading and nested relationships
        result = crud.get_items_detail(
            db=db,
            model=models.Behavior,
            skip=skip, 
            limit=limit, 
            sort_by=sort_by, 
            sort_order=sort_order, 
            filter=filter,
            nested_relationships={
                "metrics": ["metric_type", "backend_type"]
            }
        )
        print(f"✅ [DEBUG] get_items_detail returned {len(result)} behaviors")
        if result:
            print(f"🔍 [DEBUG] First item: id={result[0].id}, name={result[0].name}, metrics_count={len(result[0].metrics) if hasattr(result[0], 'metrics') else 'N/A'}")
            if hasattr(result[0], 'metrics') and result[0].metrics:
                first_metric = result[0].metrics[0]
                print(f"🔍 [DEBUG] First metric: id={first_metric.id}, name={first_metric.name}, has_metric_type={hasattr(first_metric, 'metric_type')}, has_backend_type={hasattr(first_metric, 'backend_type')}")
        return result
    except Exception as e:
        print(f"❌ [DEBUG] Error in read_behaviors: {type(e).__name__}: {str(e)}")
        print(f"❌ [DEBUG] Error traceback: {e.__class__.__module__}.{e.__class__.__name__}")
        raise


@router.get("/{behavior_id}", response_model=schemas.Behavior)
def read_behavior(
    behavior_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_behavior = crud.get_behavior(db, behavior_id=behavior_id)
    if db_behavior is None:
        raise HTTPException(status_code=404, detail="Behavior not found")
    return db_behavior


@router.delete("/{behavior_id}", response_model=schemas.Behavior)
def delete_behavior(
    behavior_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_behavior = crud.delete_behavior(db, behavior_id=behavior_id)
    if db_behavior is None:
        raise HTTPException(status_code=404, detail="Behavior not found")
    return db_behavior


@router.put("/{behavior_id}", response_model=schemas.Behavior)
def update_behavior(
    behavior_id: uuid.UUID,
    behavior: schemas.BehaviorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        db_behavior = crud.update_behavior(db, behavior_id=behavior_id, behavior=behavior)
        if db_behavior is None:
            raise HTTPException(status_code=404, detail="Behavior not found")
        return db_behavior
    except HTTPException:
        # Re-raise HTTPExceptions (like our 404)
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations (like foreign key constraints)
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            if "status_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid status reference")
            raise HTTPException(status_code=400, detail="Invalid reference in behavior data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Behavior with this name already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all metrics associated with a behavior"""
    try:
        metrics = crud.get_behavior_metrics(
            db,
            behavior_id=behavior_id,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )
        return metrics
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{behavior_id}/metrics/{metric_id}")
def add_metric_to_behavior(
    behavior_id: uuid.UUID,
    metric_id: uuid.UUID,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
        return {"status": "success", "message": "Metric was not associated with behavior"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

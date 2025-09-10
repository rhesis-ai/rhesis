import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_tenant_context
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema with metrics support and nested relationships
BehaviorWithMetricsSchema = create_detailed_schema(
    schemas.Behavior,
    models.Behavior,
    include_many_to_many=True,
    include_nested_relationships={"metrics": ["metric_type", "backend_type"]},
)
MetricDetailSchema = create_detailed_schema(schemas.Metric, models.Metric)

router = APIRouter(
    prefix="/behaviors",
    tags=["behaviors"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=BehaviorWithMetricsSchema)
@handle_database_exceptions(
    entity_name="behavior",
    custom_unique_message="Behavior with this name already exists"
)
def create_behavior(
    behavior: schemas.BehaviorCreate,
    db: Session = Depends(get_db),  # ← Uses regular database session
    tenant_context = Depends(get_tenant_context),  # ← Gets tenant context directly
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create behavior with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    
    print(f"🚀 [OPTIMIZED] Creating behavior with direct tenant context")
    print(f"🔍 [OPTIMIZED] Organization: {organization_id}, User: {user_id}")
    result = crud.create_behavior(
        db=db, 
        behavior=behavior,
        organization_id=organization_id,
        user_id=user_id
    )
    print(f"✅ [OPTIMIZED] Successfully created behavior: {result.id}")
    return result


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
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get all behaviors with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    
    print(f"🔍 [OPTIMIZED] Behaviors endpoint called with params: skip={skip}, limit={limit}, sort_by={sort_by}, sort_order={sort_order}, filter={filter}")
    print(f"🔍 [OPTIMIZED] Direct tenant context: org={organization_id}, user={user_id}")

    try:
        print(f"🔍 [OPTIMIZED] Using optimized relationship loading with direct tenant context...")
        # Use get_items_detail with optimized loading and direct tenant context
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
            },
            organization_id=organization_id,
            user_id=user_id
        )
        print(f"✅ [DEBUG] get_items_detail returned {len(result)} behaviors")
        if result:
            print(
                f"🔍 [DEBUG] First item: id={result[0].id}, name={result[0].name}, metrics_count={len(result[0].metrics) if hasattr(result[0], 'metrics') else 'N/A'}"
            )
            if hasattr(result[0], "metrics") and result[0].metrics:
                first_metric = result[0].metrics[0]
                print(
                    f"🔍 [DEBUG] First metric: id={first_metric.id}, name={first_metric.name}, has_metric_type={hasattr(first_metric, 'metric_type')}, has_backend_type={hasattr(first_metric, 'backend_type')}"
                )
        return result
    except Exception as e:
        print(f"❌ [DEBUG] Error in read_behaviors: {type(e).__name__}: {str(e)}")
        print(f"❌ [DEBUG] Error traceback: {e.__class__.__module__}.{e.__class__.__name__}")
        raise


@router.get("/{behavior_id}")
def read_behavior(
    behavior_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get behavior with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_behavior = crud.get_behavior(db, behavior_id=behavior_id)
    if db_behavior is None:
        raise HTTPException(status_code=404, detail="Behavior not found")
    return db_behavior


@router.delete("/{behavior_id}")
def delete_behavior(
    behavior_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete behavior with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_behavior = crud.delete_behavior(db, behavior_id=behavior_id)
    if db_behavior is None:
        raise HTTPException(status_code=404, detail="Behavior not found")
    return db_behavior


@router.put("/{behavior_id}", response_model=BehaviorWithMetricsSchema)
@handle_database_exceptions(
    entity_name="behavior",
    custom_unique_message="Behavior with this name already exists"
)
def update_behavior(
    behavior_id: uuid.UUID,
    behavior: schemas.BehaviorUpdate,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update behavior with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_behavior = crud.update_behavior(
        db, 
        behavior_id=behavior_id, 
        behavior=behavior,
        organization_id=organization_id,
        user_id=user_id
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

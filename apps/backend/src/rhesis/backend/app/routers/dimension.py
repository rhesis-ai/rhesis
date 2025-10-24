import uuid

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

router = APIRouter(
    prefix="/dimensions",
    tags=["dimensions"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Dimension)
@handle_database_exceptions(
    entity_name="dimension", custom_unique_message="Dimension with this name already exists"
)
def create_dimension(
    dimension: schemas.DimensionCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create dimension with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_dimension(
        db=db, dimension=dimension, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.Dimension])
@with_count_header(model=models.Dimension)
def read_dimensions(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all dimensions with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_dimensions(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{dimension_id}", response_model=schemas.Dimension)
def read_dimension(
    dimension_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_dimension = crud.get_dimension(
        db, dimension_id=dimension_id, organization_id=organization_id, user_id=user_id
    )
    if db_dimension is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_dimension


@router.delete("/{dimension_id}", response_model=schemas.Dimension)
def delete_dimension(
    dimension_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_dimension = crud.delete_dimension(
        db, dimension_id=dimension_id, organization_id=organization_id, user_id=user_id
    )
    if db_dimension is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_dimension


@router.put("/{dimension_id}", response_model=schemas.Dimension)
def update_dimension(
    dimension_id: uuid.UUID,
    dimension: schemas.DimensionUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_dimension = crud.update_dimension(
        db,
        dimension_id=dimension_id,
        dimension=dimension,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_dimension is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_dimension

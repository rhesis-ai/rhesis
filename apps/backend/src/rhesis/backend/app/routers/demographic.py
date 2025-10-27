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
    prefix="/demographics",
    tags=["demographics"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Demographic)
@handle_database_exceptions(
    entity_name="demographic", custom_unique_message="Demographic with this name already exists"
)
def create_demographic(
    demographic: schemas.DemographicCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create demographic with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_demographic(
        db=db, demographic=demographic, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.Demographic])
@with_count_header(model=models.Demographic)
def read_demographics(
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
    """Get all demographics with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_demographics(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{demographic_id}", response_model=schemas.Demographic)
def read_demographic(
    demographic_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_demographic = crud.get_demographic(
        db, demographic_id=demographic_id, organization_id=organization_id, user_id=user_id
    )
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Demographic not found")
    return db_demographic


@router.delete("/{demographic_id}", response_model=schemas.Demographic)
def delete_demographic(
    demographic_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_demographic = crud.delete_demographic(
        db, demographic_id=demographic_id, organization_id=organization_id, user_id=user_id
    )
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Demographic not found")
    return db_demographic


@router.put("/{demographic_id}", response_model=schemas.Demographic)
def update_demographic(
    demographic_id: uuid.UUID,
    demographic: schemas.DemographicUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update demographic with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_demographic = crud.update_demographic(
        db,
        demographic_id=demographic_id,
        demographic=demographic,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Demographic not found")
    return db_demographic

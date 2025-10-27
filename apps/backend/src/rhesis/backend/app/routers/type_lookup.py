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
    prefix="/type_lookups",
    tags=["type_lookups"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@handle_database_exceptions(
    entity_name="type_lookup", custom_unique_message="type_lookup.py with this name already exists"
)
@router.post("/", response_model=schemas.TypeLookup)
def create_type_lookup(
    type_lookup: schemas.TypeLookupCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create type lookup with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_type_lookup(
        db=db, type_lookup=type_lookup, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.TypeLookup])
@with_count_header(model=models.TypeLookup)
def read_type_lookups(
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
    """Get all type lookups with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_type_lookups(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{type_lookup_id}")
def read_type_lookup(
    type_lookup_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get type_lookup with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_type_lookup = crud.get_type_lookup(
        db, type_lookup_id=type_lookup_id, organization_id=organization_id, user_id=user_id
    )
    if db_type_lookup is None:
        raise HTTPException(status_code=404, detail="TypeLookup not found")
    return db_type_lookup


@router.delete("/{type_lookup_id}")
def delete_type_lookup(
    type_lookup_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete type_lookup with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_type_lookup = crud.delete_type_lookup(
        db, type_lookup_id=type_lookup_id, organization_id=organization_id, user_id=user_id
    )
    if db_type_lookup is None:
        raise HTTPException(status_code=404, detail="Type Lookup not found")
    return db_type_lookup


@router.put("/{type_lookup_id}", response_model=schemas.TypeLookup)
def update_type_lookup(
    type_lookup_id: uuid.UUID,
    type_lookup: schemas.TypeLookupUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update type_lookup with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_type_lookup = crud.update_type_lookup(
        db,
        type_lookup_id=type_lookup_id,
        type_lookup=type_lookup,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_type_lookup is None:
        raise HTTPException(status_code=404, detail="TypeLookup not found")
    return db_type_lookup

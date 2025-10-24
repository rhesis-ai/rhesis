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
    prefix="/response_patterns",
    tags=["response_patterns"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@handle_database_exceptions(
    entity_name="response_pattern",
    custom_unique_message="response_pattern.py with this name already exists",
)
@router.post("/", response_model=schemas.ResponsePattern)
def create_response_pattern(
    response_pattern: schemas.ResponsePatternCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create response pattern with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_response_pattern(
        db=db, response_pattern=response_pattern, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.ResponsePattern])
@with_count_header(model=models.ResponsePattern)
def read_response_patterns(
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
    """Get all response patterns with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_response_patterns(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{response_pattern_id}", response_model=schemas.ResponsePattern)
def read_response_pattern(
    response_pattern_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_response_pattern = crud.get_response_pattern(
        db,
        response_pattern_id=response_pattern_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_response_pattern is None:
        raise HTTPException(status_code=404, detail="Response Pattern not found")
    return db_response_pattern


@router.put("/{response_pattern_id}", response_model=schemas.ResponsePattern)
def update_response_pattern(
    response_pattern_id: uuid.UUID,
    response_pattern: schemas.ResponsePatternUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_response_pattern = crud.update_response_pattern(
        db,
        response_pattern_id=response_pattern_id,
        response_pattern=response_pattern,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_response_pattern is None:
        raise HTTPException(status_code=404, detail="Response Pattern not found")
    return db_response_pattern


@router.delete("/{response_pattern_id}", response_model=schemas.ResponsePattern)
def delete_response_pattern(
    response_pattern_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_response_pattern = crud.delete_response_pattern(
        db,
        response_pattern_id=response_pattern_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_response_pattern is None:
        raise HTTPException(status_code=404, detail="Response Pattern not found")
    return db_response_pattern

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
    prefix="/use_cases",
    tags=["use_cases"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@handle_database_exceptions(
    entity_name="use_case", custom_unique_message="use_case.py with this name already exists"
)
@router.post("/", response_model=schemas.UseCase)
def create_use_case(
    use_case: schemas.UseCaseCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create use case with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_use_case(
        db=db, use_case=use_case, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.UseCase])
@with_count_header(model=models.UseCase)
def read_use_cases(
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
    """Get all use cases with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_use_cases(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{use_case_id}")
def read_use_case(
    use_case_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get use_case with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_use_case = crud.get_use_case(
        db, use_case_id=use_case_id, organization_id=organization_id, user_id=user_id
    )
    if db_use_case is None:
        raise HTTPException(status_code=404, detail="Use case not found")
    return db_use_case


@router.delete("/{use_case_id}")
def delete_use_case(
    use_case_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete use_case with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_use_case = crud.delete_use_case(
        db, use_case_id=use_case_id, organization_id=organization_id, user_id=user_id
    )
    if db_use_case is None:
        raise HTTPException(status_code=404, detail="Use case not found")
    return db_use_case


@router.put("/{use_case_id}", response_model=schemas.UseCase)
def update_use_case(
    use_case_id: uuid.UUID,
    use_case: schemas.UseCaseUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update use_case with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_use_case = crud.update_use_case(
        db,
        use_case_id=use_case_id,
        use_case=use_case,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_use_case is None:
        raise HTTPException(status_code=404, detail="Use case not found")
    return db_use_case

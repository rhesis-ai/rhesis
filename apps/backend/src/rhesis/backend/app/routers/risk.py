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
    prefix="/risks",
    tags=["risks"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Risk)
@handle_database_exceptions(
    entity_name="risk", custom_unique_message="Risk with this name already exists"
)
def create_risk(
    risk: schemas.RiskCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create risk with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_risk(db=db, risk=risk, organization_id=organization_id, user_id=user_id)


@router.get("/", response_model=list[schemas.Risk])
@with_count_header(model=models.Risk)
def read_risks(
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
    """Get all risks with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_risks(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{risk_id}", response_model=schemas.Risk)
def read_risk(
    risk_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_risk = crud.get_risk(db, risk_id=risk_id, organization_id=organization_id, user_id=user_id)
    if db_risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return db_risk


@router.delete("/{risk_id}", response_model=schemas.Risk)
def delete_risk(
    risk_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_risk = crud.delete_risk(
        db, risk_id=risk_id, organization_id=organization_id, user_id=user_id
    )
    if db_risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return db_risk


@router.put("/{risk_id}", response_model=schemas.Risk)
def update_risk(
    risk_id: uuid.UUID,
    risk: schemas.RiskUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update risk with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_risk = crud.update_risk(
        db, risk_id=risk_id, risk=risk, organization_id=organization_id, user_id=user_id
    )
    if db_risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return db_risk

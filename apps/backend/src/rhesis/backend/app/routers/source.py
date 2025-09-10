import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_tenant_context
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions

router = APIRouter(
    prefix="/sources",
    tags=["sources"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Source)
@handle_database_exceptions(
    entity_name="source",
    custom_unique_message="Source with this name already exists"
)
def create_source(
    source: schemas.SourceCreate,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create source with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_source(
        db=db,
        source=source,
        organization_id=organization_id,
        user_id=user_id
    )


@router.get("/", response_model=list[schemas.Source])
@with_count_header(model=models.Source)
def read_sources(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all sources with their related objects"""
    return crud.get_sources(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{source_id}")
def read_source(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get source with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_source = crud.get_source(db, source_id=source_id)
    if db_source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return db_source


@router.delete("/{source_id}")
def delete_source(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete source with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_source = crud.delete_source(db, source_id=source_id)
    if db_source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return db_source


@router.put("/{source_id}", response_model=schemas.Source)
def update_source(
    source_id: uuid.UUID,
    source: schemas.SourceUpdate,
    db: Session = Depends(get_db),
    tenant_context = Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update source with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_source = crud.update_source(db, source_id=source_id, source=source)
    if db_source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return db_source

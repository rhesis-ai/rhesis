import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.odata import combine_entity_type_filter
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for Test
StatusDetailSchema = create_detailed_schema(schemas.Status, models.Status)

router = APIRouter(
    prefix="/statuses",
    tags=["statuses"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=StatusDetailSchema)
def create_status(
    status: schemas.StatusCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    return crud.create_status(db=db, status=status)


@router.get("/", response_model=list[StatusDetailSchema])
@with_count_header(model=models.Status)
def read_statuses(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    entity_type: str | None = Query(None, description="Filter statuses by entity type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all statuses with their related objects"""
    filter = combine_entity_type_filter(filter, entity_type)

    return crud.get_statuses(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{status_id}", response_model=StatusDetailSchema)
def read_status(
    status_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_status = crud.get_status(db, status_id=status_id)
    if db_status is None:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status


@router.delete("/{status_id}", response_model=schemas.Status)
def delete_status(
    status_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_status = crud.delete_status(db, status_id=status_id)
    if db_status is None:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status


@router.put("/{status_id}", response_model=schemas.Status)
def update_status(
    status_id: uuid.UUID,
    status: schemas.StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_status = crud.update_status(db, status_id=status_id, status=status)
    if db_status is None:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status

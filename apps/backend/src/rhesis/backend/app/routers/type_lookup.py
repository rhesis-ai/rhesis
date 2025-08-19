import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/type_lookups",
    tags=["type_lookups"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.TypeLookup)
def create_type_lookup(
    type_lookup: schemas.TypeLookupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    return crud.create_type_lookup(db=db, type_lookup=type_lookup)


@router.get("/", response_model=list[schemas.TypeLookup])
@with_count_header(model=models.TypeLookup)
def read_type_lookups(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all type lookups with their related objects"""
    return crud.get_type_lookups(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{type_lookup_id}", response_model=schemas.TypeLookup)
def read_type_lookup(
    type_lookup_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_type_lookup = crud.get_type_lookup(db, type_lookup_id=type_lookup_id)
    if db_type_lookup is None:
        raise HTTPException(status_code=404, detail="TypeLookup not found")
    return db_type_lookup


@router.delete("/{type_lookup_id}", response_model=schemas.TypeLookup)
def delete_type_lookup(
    type_lookup_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_type_lookup = crud.delete_type_lookup(db, type_lookup_id=type_lookup_id)
    if db_type_lookup is None:
        raise HTTPException(status_code=404, detail="Type Lookup not found")
    return db_type_lookup


@router.put("/{type_lookup_id}", response_model=schemas.TypeLookup)
def update_type_lookup(
    type_lookup_id: uuid.UUID,
    type_lookup: schemas.TypeLookupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_type_lookup = crud.update_type_lookup(
        db, type_lookup_id=type_lookup_id, type_lookup=type_lookup
    )
    if db_type_lookup is None:
        raise HTTPException(status_code=404, detail="TypeLookup not found")
    return db_type_lookup

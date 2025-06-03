import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/dimensions",
    tags=["dimensions"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Dimension)
def create_demographic(demographic: schemas.DimensionCreate, db: Session = Depends(get_db)):
    return crud.create_demographic(db=db, demographic=demographic)


@router.get("/", response_model=list[schemas.Dimension])
@with_count_header(model=models.Dimension)
def read_dimensions(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
):
    """Get all dimensions with their related objects"""
    return crud.get_dimensions(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{demographic_id}", response_model=schemas.Dimension)
def read_demographic(demographic_id: str, db: Session = Depends(get_db)):
    db_demographic = crud.get_demographic(db, demographic_id=demographic_id)
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_demographic


@router.delete("/{demographic_id}", response_model=schemas.Behavior)
def delete_demographic(demographic_id: uuid.UUID, db: Session = Depends(get_db)):
    db_demographic = crud.delete_demographic(db, demographic_id=demographic_id)
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_demographic


@router.put("/{demographic_id}", response_model=schemas.Dimension)
def update_demographic(
    demographic_id: uuid.UUID, demographic: schemas.DimensionUpdate, db: Session = Depends(get_db)
):
    db_demographic = crud.update_demographic(
        db, demographic_id=demographic_id, demographic=demographic
    )
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_demographic

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.models.user import User

router = APIRouter(
    prefix="/dimensions",
    tags=["dimensions"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Dimension)
def create_dimension(dimension: schemas.DimensionCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_dimension(db=db, dimension=dimension)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations (like foreign key constraints)
        error_msg = str(e)
        if "foreign key constraint" in error_msg.lower() or "violates foreign key" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Invalid reference in dimension data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Dimension with this name already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


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


@router.get("/{dimension_id}", response_model=schemas.Dimension)
def read_dimension(dimension_id: uuid.UUID, db: Session = Depends(get_db)):
    db_dimension = crud.get_dimension(db, dimension_id=dimension_id)
    if db_dimension is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_dimension


@router.delete("/{dimension_id}", response_model=schemas.Dimension)
def delete_dimension(dimension_id: uuid.UUID, db: Session = Depends(get_db)):
    db_dimension = crud.delete_dimension(db, dimension_id=dimension_id)
    if db_dimension is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_dimension


@router.put("/{dimension_id}", response_model=schemas.Dimension)
def update_dimension(
    dimension_id: uuid.UUID, dimension: schemas.DimensionUpdate, db: Session = Depends(get_db)
):
    db_dimension = crud.update_dimension(
        db, dimension_id=dimension_id, dimension=dimension
    )
    if db_dimension is None:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return db_dimension

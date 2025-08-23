import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/demographics",
    tags=["demographics"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Demographic)
def create_demographic(demographic: schemas.DemographicCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_demographic(db=db, demographic=demographic)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations (like foreign key constraints)
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            if "dimension_id" in error_msg.lower():
                raise HTTPException(status_code=400, detail="Invalid dimension reference")
            raise HTTPException(status_code=400, detail="Invalid reference in demographic data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Demographic with this name already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=list[schemas.Demographic])
@with_count_header(model=models.Demographic)
def read_demographics(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
):
    """Get all demographics with their related objects"""
    return crud.get_demographics(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{demographic_id}", response_model=schemas.Demographic)
def read_demographic(demographic_id: uuid.UUID, db: Session = Depends(get_db)):
    db_demographic = crud.get_demographic(db, demographic_id=demographic_id)
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Demographic not found")
    return db_demographic


@router.delete("/{demographic_id}", response_model=schemas.Demographic)
def delete_demographic(demographic_id: uuid.UUID, db: Session = Depends(get_db)):
    db_demographic = crud.delete_demographic(db, demographic_id=demographic_id)
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Demographic not found")
    return db_demographic


@router.put("/{demographic_id}", response_model=schemas.Demographic)
def update_demographic(
    demographic_id: uuid.UUID, demographic: schemas.DemographicUpdate, db: Session = Depends(get_db)
):
    db_demographic = crud.update_demographic(
        db, demographic_id=demographic_id, demographic=demographic
    )
    if db_demographic is None:
        raise HTTPException(status_code=404, detail="Demographic not found")
    return db_demographic

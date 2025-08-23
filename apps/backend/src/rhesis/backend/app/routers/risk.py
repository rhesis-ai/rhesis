import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/risks",
    tags=["risks"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Risk)
def create_risk(risk: schemas.RiskCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_risk(db=db, risk=risk)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations (like foreign key constraints)
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            raise HTTPException(status_code=400, detail="Invalid reference in risk data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Risk with this name already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=list[schemas.Risk])
@with_count_header(model=models.Risk)
def read_risks(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
):
    """Get all risks with their related objects"""
    return crud.get_risks(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{risk_id}", response_model=schemas.Risk)
def read_risk(risk_id: uuid.UUID, db: Session = Depends(get_db)):
    db_risk = crud.get_risk(db, risk_id=risk_id)
    if db_risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return db_risk


@router.delete("/{risk_id}", response_model=schemas.Risk)
def delete_risk(risk_id: uuid.UUID, db: Session = Depends(get_db)):
    db_risk = crud.delete_risk(db, risk_id=risk_id)
    if db_risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return db_risk


@router.put("/{risk_id}", response_model=schemas.Risk)
def update_risk(risk_id: uuid.UUID, risk: schemas.RiskUpdate, db: Session = Depends(get_db)):
    db_risk = crud.update_risk(db, risk_id=risk_id, risk=risk)
    if db_risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return db_risk

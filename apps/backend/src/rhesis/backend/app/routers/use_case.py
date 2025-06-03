import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/use_cases",
    tags=["use_cases"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.UseCase)
def create_use_case(
    use_case: schemas.UseCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    return crud.create_use_case(db=db, use_case=use_case)


@router.get("/", response_model=list[schemas.UseCase])
@with_count_header(model=models.UseCase)
def read_use_cases(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all use cases with their related objects"""
    return crud.get_use_cases(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{use_case_id}", response_model=schemas.UseCase)
def read_use_case(
    use_case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_use_case = crud.get_use_case(db, use_case_id=use_case_id)
    if db_use_case is None:
        raise HTTPException(status_code=404, detail="Use case not found")
    return db_use_case


@router.delete("/{use_case_id}", response_model=schemas.UseCase)
def delete_use_case(
    use_case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_use_case = crud.delete_use_case(db, use_case_id=use_case_id)
    if db_use_case is None:
        raise HTTPException(status_code=404, detail="Use case not found")
    return db_use_case


@router.put("/{use_case_id}", response_model=schemas.UseCase)
def update_use_case(
    use_case_id: uuid.UUID,
    use_case: schemas.UseCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_use_case = crud.update_use_case(db, use_case_id=use_case_id, use_case=use_case)
    if db_use_case is None:
        raise HTTPException(status_code=404, detail="Use case not found")
    return db_use_case

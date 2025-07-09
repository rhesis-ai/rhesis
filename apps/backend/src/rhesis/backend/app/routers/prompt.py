import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.models.user import User

router = APIRouter(
    prefix="/prompts",
    tags=["prompts"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Prompt)
def create_prompt(prompt: schemas.PromptCreate, db: Session = Depends(get_db)):
    return crud.create_prompt(db=db, prompt=prompt)


@router.get("/", response_model=list[schemas.Prompt])
@with_count_header(model=models.Prompt)
def read_prompts(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
):
    """Get all prompts with their related objects"""
    return crud.get_prompts(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{prompt_id}", response_model=schemas.Prompt)
def read_prompt(prompt_id: uuid.UUID, db: Session = Depends(get_db)):
    db_prompt = crud.get_prompt(db, prompt_id=prompt_id)
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return db_prompt


@router.put("/{prompt_id}", response_model=schemas.Prompt)
def update_prompt(
    prompt_id: uuid.UUID, prompt: schemas.PromptUpdate, db: Session = Depends(get_db)
):
    """Update a prompt"""
    db_prompt = crud.update_prompt(db=db, prompt_id=prompt_id, prompt=prompt)
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return db_prompt


@router.delete("/{prompt_id}", response_model=schemas.Prompt)
def delete_prompt(prompt_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a prompt"""
    db_prompt = crud.delete_prompt(db=db, prompt_id=prompt_id)
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return db_prompt

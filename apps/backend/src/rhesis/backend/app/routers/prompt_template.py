import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.models.user import User

router = APIRouter(
    prefix="/prompt_templates",
    tags=["prompt_templates"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.PromptTemplate)
def create_prompt_template(template: schemas.PromptTemplate, db: Session = Depends(get_db)):
    return crud.create_prompt_template(db=db, template=template)


@router.get("/", response_model=list[schemas.PromptTemplate])
@with_count_header(model=models.PromptTemplate)
def read_prompt_templates(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
):
    """Get all prompt templates with their related objects"""
    return crud.get_prompt_templates(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{prompt_template_id}", response_model=schemas.PromptTemplate)
def read_prompt_template(prompt_template_id: uuid.UUID, db: Session = Depends(get_db)):
    db_template = crud.get_prompt_template(db, prompt_template_id=prompt_template_id)
    if db_template is None:
        raise HTTPException(status_code=404, detail="Prompt Template not found")
    return db_template


@router.delete("/{prompt_template_id}", response_model=schemas.PromptTemplate)
def delete_prompt_template(prompt_template_id: uuid.UUID, db: Session = Depends(get_db)):
    db_prompt_template = crud.delete_prompt_template(db, prompt_template_id=prompt_template_id)
    if db_prompt_template is None:
        raise HTTPException(status_code=404, detail="Prompt Template not found")
    return db_prompt_template


@router.put("/{prompt_template_id}", response_model=schemas.PromptTemplate)
def update_prompt_template(
    prompt_template_id: uuid.UUID,
    prompt_template: schemas.PromptTemplateUpdate,
    db: Session = Depends(get_db),
):
    db_prompt_template = crud.update_prompt_template(
        db, prompt_template_id=prompt_template_id, prompt_template=prompt_template
    )
    if db_prompt_template is None:
        raise HTTPException(status_code=404, detail="Prompt Template not found")
    return db_prompt_template

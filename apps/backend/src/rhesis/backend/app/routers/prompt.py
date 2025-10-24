import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/prompts",
    tags=["prompts"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@handle_database_exceptions(
    entity_name="prompt", custom_unique_message="prompt.py with this name already exists"
)
@router.post("/", response_model=schemas.Prompt)
def create_prompt(
    prompt: schemas.PromptCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user=Depends(require_current_user_or_token),
):
    """
    Create prompt with super optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_prompt(
        db=db, prompt=prompt, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.Prompt])
@with_count_header(model=models.Prompt)
def read_prompts(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all prompts with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_prompts(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{prompt_id}", response_model=schemas.Prompt)
def read_prompt(
    prompt_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_prompt = crud.get_prompt(
        db, prompt_id=prompt_id, organization_id=organization_id, user_id=user_id
    )
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return db_prompt


@router.put("/{prompt_id}", response_model=schemas.Prompt)
def update_prompt(
    prompt_id: uuid.UUID,
    prompt: schemas.PromptUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update a prompt"""
    organization_id, user_id = tenant_context
    db_prompt = crud.update_prompt(
        db=db, prompt_id=prompt_id, prompt=prompt, organization_id=organization_id, user_id=user_id
    )
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return db_prompt


@router.delete("/{prompt_id}", response_model=schemas.Prompt)
def delete_prompt(
    prompt_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a prompt"""
    organization_id, user_id = tenant_context
    db_prompt = crud.delete_prompt(
        db=db, prompt_id=prompt_id, organization_id=organization_id, user_id=user_id
    )
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return db_prompt

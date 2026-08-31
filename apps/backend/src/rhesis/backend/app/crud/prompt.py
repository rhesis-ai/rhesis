"""CRUD operations for prompts and prompt templates.

Prompt templates live here too rather than in their own module: a template is a prompt with
placeholders left in, so it is the same domain.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item,
    get_items,
    get_items_detail,
    update_item,
)


def get_prompt(
    db: Session,
    prompt_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Prompt]:
    """Get prompt."""
    return get_item(db, models.Prompt, prompt_id, organization_id, user_id)


def get_prompts(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.Prompt]:
    # PromptDetail has no nested relationship fields -- plain get_items, no eager load.
    return get_items(
        db,
        models.Prompt,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_prompt(
    db: Session,
    prompt: schemas.PromptCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.Prompt:
    """Create prompt."""
    return create_item(db, models.Prompt, prompt, organization_id, user_id)


def update_prompt(
    db: Session,
    prompt_id: uuid.UUID,
    prompt: schemas.PromptUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.Prompt]:
    """Update prompt."""
    return update_item(db, models.Prompt, prompt_id, prompt, organization_id, user_id)


def delete_prompt(
    db: Session, prompt_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Prompt]:
    return delete_item(
        db, models.Prompt, prompt_id, organization_id=organization_id, user_id=user_id
    )


# Prompt Template CRUD
def get_prompt_template(
    db: Session, prompt_template_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.PromptTemplate]:
    return get_item(db, models.PromptTemplate, prompt_template_id, organization_id, user_id)


def get_prompt_templates(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.PromptTemplate]:
    return get_items_detail(
        db,
        models.PromptTemplate,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_prompt_template(
    db: Session,
    prompt_template: schemas.PromptTemplateCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.PromptTemplate:
    """Create prompt template."""
    return create_item(db, models.PromptTemplate, prompt_template, organization_id, user_id)


def update_prompt_template(
    db: Session,
    prompt_template_id: uuid.UUID,
    prompt_template: schemas.PromptTemplateUpdate,
    organization_id: str,
    user_id: str,
) -> Optional[models.PromptTemplate]:
    return update_item(
        db, models.PromptTemplate, prompt_template_id, prompt_template, organization_id, user_id
    )


def delete_prompt_template(
    db: Session, prompt_template_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.PromptTemplate]:
    return delete_item(db, models.PromptTemplate, prompt_template_id, organization_id, user_id)

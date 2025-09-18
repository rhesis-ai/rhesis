from typing import List, Optional

from pydantic import UUID4

from rhesis.backend.app.schemas.base import Base
from rhesis.backend.app.schemas.tag import Tag


# Template schemas
class PromptTemplateBase(Base):
    content: str
    category_id: Optional[UUID4] = None
    topic_id: Optional[UUID4] = None
    parent_id: Optional[UUID4] = None
    language_code: Optional[str] = None
    is_summary: Optional[bool] = False
    source_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    tags: Optional[List[Tag]] = None


class PromptTemplateCreate(PromptTemplateBase):
    pass


class PromptTemplateUpdate(PromptTemplateBase):
    content: Optional[str] = None
    language_code: Optional[str] = None


class PromptTemplate(PromptTemplateBase):
    pass

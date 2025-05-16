from typing import List, Optional

from pydantic import UUID4

from rhesis.backend.app.schemas.base import Base
from rhesis.backend.app.schemas.tag import Tag


# Base Prompt Schema
class PromptBase(Base):
    content: str
    demographic_id: Optional[UUID4] = None
    category_id: Optional[UUID4] = None
    attack_category_id: Optional[UUID4] = None
    topic_id: Optional[UUID4] = None
    language_code: str
    behavior_id: Optional[UUID4] = None
    parent_id: Optional[UUID4] = None  # for multiturn scenarios
    prompt_template_id: Optional[UUID4] = None
    expected_response: Optional[str] = None
    source_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    tags: Optional[List[Tag]] = None


# Prompt Create schema
class PromptCreate(PromptBase):
    pass


# Prompt Update schema - extending PromptBase
class PromptUpdate(PromptBase):
    content: Optional[str] = None  # Override to make 'text' optional for updates
    language_code: Optional[str] = None  # Override to make 'language_code' optional for updates


# Read schema (optional, if it contains extra fields)
class Prompt(PromptBase):
    pass


class PromptView(Base):
    content: str
    demographic: Optional[str] = None
    category: Optional[str] = None
    attack_category: Optional[str] = None
    topic: Optional[str] = None
    language_code: str
    behavior: Optional[str] = None
    expected_response: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None

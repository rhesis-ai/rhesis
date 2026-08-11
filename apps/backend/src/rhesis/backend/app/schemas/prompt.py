from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas.base import Base


# Base Prompt Schema
class PromptBase(Base):
    content: str
    category_id: Optional[UUID4] = None
    topic_id: Optional[UUID4] = None
    language_code: str
    behavior_id: Optional[UUID4] = None
    expected_response: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None


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

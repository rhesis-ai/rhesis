from datetime import datetime
from typing import List, Literal, Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict, Field

from rhesis.backend.app.schemas.annotation import AnnotationDetail, AnnotationTuningCase
from rhesis.backend.app.schemas.base import Base, ServerIdentity
from rhesis.backend.app.schemas.tag import Tag, TagRead
from rhesis.backend.app.schemas.user import UserReference


# Requirement schemas
class RequirementBase(Base):
    name: str
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    parent_id: Optional[UUID4] = None
    impact_id: Optional[UUID4] = None


class RequirementCreate(RequirementBase):
    pass


class RequirementUpdate(RequirementBase):
    name: Optional[str] = None


class Requirement(RequirementBase, ServerIdentity):
    tags: List[Tag] = Field(default_factory=list)
    created_at: Optional[Union[datetime, str]] = None
    updated_at: Optional[Union[datetime, str]] = None
    user: Optional[UserReference] = None


class RequirementTestCounts(BaseModel):
    """How many tests are linked to a requirement, by test type."""

    total: int = 0
    single_turn: int = 0
    multi_turn: int = 0


class RequirementParentRef(BaseModel):
    id: UUID4
    name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RequirementLookupRef(BaseModel):
    id: UUID4
    type_name: Optional[str] = None
    type_value: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RequirementSourceTypeRef(BaseModel):
    id: UUID4
    type_value: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RequirementSourceRef(BaseModel):
    """A linked source, with the note stored on the link."""

    id: UUID4
    title: Optional[str] = None
    url: Optional[str] = None
    source_type: Optional[RequirementSourceTypeRef] = None
    note: Optional[str] = None


class RequirementSourceLink(BaseModel):
    note: Optional[str] = None


RequirementTuningCaseRef = AnnotationTuningCase


class RequirementReviewHint(BaseModel):
    kind: Literal["vague_wording", "unclear_behavior", "split", "other"]
    message: str
    quote: Optional[str] = None
    suggestion: Optional[str] = None


class RequirementReview(BaseModel):
    reviewed_at: str
    description_hash: str
    hints: List[RequirementReviewHint] = Field(default_factory=list)


class RequirementExample(BaseModel):
    """An annotation linked to a requirement, with the exchange it judged."""

    annotation: AnnotationDetail
    input: Optional[str] = None
    output: Optional[str] = None
    tuning_cases: List[RequirementTuningCaseRef] = Field(default_factory=list)


# The detailed model with expanded relations.
class RequirementDetail(Requirement):
    # Override of the base schema's tags field to match the shape used for the
    # detailed/expanded response (TagRead instead of Tag).
    id: UUID4
    name: Optional[str] = None
    tags: Optional[List[TagRead]] = None

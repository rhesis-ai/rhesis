import datetime
from typing import Any, ClassVar, Dict, Optional, Union
from uuid import UUID

from pydantic import ConfigDict, Field

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.constants import AnnotationTarget, EntityType
from rhesis.backend.app.schemas.affordances import WithPermittedActions
from rhesis.backend.app.schemas.base import Base, ServerIdentity
from rhesis.backend.app.schemas.test import UserReference


class AnnotationTargetSchema(Base):
    type: AnnotationTarget = Field(
        ...,
        description="What is being annotated: 'test_result', 'trace', 'test', 'turn' or 'metric'",
    )
    reference: Optional[str] = Field(
        None,
        description="Metric name for 'metric', 'Turn N' for 'turn'; null for entity-level targets",
    )

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class AnnotationCreate(Base):
    entity_type: EntityType = Field(
        ..., description="Type of entity annotated: 'TestResult', 'Trace' or 'Test'"
    )
    entity_id: UUID = Field(..., description="ID of the entity being annotated")
    status_id: UUID = Field(..., description="Status UUID carrying the verdict")
    comments: Optional[str] = Field(None, description="Annotation comments")
    target: Optional[AnnotationTargetSchema] = Field(
        None,
        description="Target within the entity; defaults to the entity-level target",
    )
    attributes: Optional[Dict[str, Any]] = Field(
        None, description="Extra structured fields carried by the annotation"
    )

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class AnnotationUpdate(Base):
    status_id: Optional[UUID] = Field(None, description="Updated status UUID")
    comments: Optional[str] = Field(None, description="Updated comments")
    target: Optional[AnnotationTargetSchema] = Field(None, description="Updated target")
    resolved: Optional[bool] = Field(None, description="Mark as resolved or reopen")
    attributes: Optional[Dict[str, Any]] = Field(None, description="Updated attributes")

    model_config = ConfigDict(from_attributes=True)


class StatusReference(Base):
    id: UUID
    name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Annotation(Base, WithPermittedActions, ServerIdentity):
    """Annotation response with server-resolved object-level affordances."""

    __resource_type__: ClassVar[Optional[str]] = ResourceType.ANNOTATION

    id: UUID
    entity_type: str
    entity_id: UUID
    target_type: str
    target_reference: Optional[str] = None
    status_id: UUID
    status: Optional[StatusReference] = None
    user_id: UUID
    user: Optional[UserReference] = None
    comments: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[Union[datetime.datetime, str]] = None
    resolved_by_id: Optional[UUID] = None
    resolved_by: Optional[UserReference] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: Union[datetime.datetime, str]
    updated_at: Union[datetime.datetime, str]

    model_config = ConfigDict(from_attributes=True)


class AnnotationContext(Base):
    """Where an annotated entity sits, so a client can build a deep link to it."""

    project_id: Optional[UUID] = None
    test_run_id: Optional[UUID] = None
    test_run_name: Optional[str] = None
    test_set_id: Optional[UUID] = None
    test_result_id: Optional[UUID] = None
    requirement_id: Optional[UUID] = None
    requirement_name: Optional[str] = None
    trace_id: Optional[str] = None
    trace_db_id: Optional[UUID] = None
    span_name: Optional[str] = None


class AnnotationDetail(Annotation):
    context: Optional[AnnotationContext] = None

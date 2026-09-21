import datetime
from typing import Any, ClassVar, Dict, Optional, Union
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def _sub_targets_need_a_reference(self) -> "AnnotationTargetSchema":
        """A metric or turn target is meaningless without naming which one.

        Rejected here rather than downstream: the override writers look the
        reference up by name, and a null one reaches ``_normalize_metric_name``
        as ``None.lower()``, which is a 500 rather than a bad request. The UI
        cannot produce this (a target only exists there once a mention names
        it), but the SDK and the MCP tools take the target as an argument.
        """
        if (
            self.type in (AnnotationTarget.METRIC, AnnotationTarget.TURN)
            and not (self.reference or "").strip()
        ):
            raise ValueError(f"target.reference is required when target.type is '{self.type}'")
        return self


class AnnotationCreate(Base):
    entity_type: EntityType = Field(
        ..., description="Type of entity annotated: 'TestResult', 'Trace' or 'Test'"
    )
    entity_id: Optional[UUID] = Field(
        None,
        description=(
            "ID of the entity being annotated. Required unless 'trace_id' names a trace instead"
        ),
    )
    trace_id: Optional[str] = Field(
        None,
        min_length=32,
        max_length=32,
        pattern=r"^[0-9a-fA-F]{32}$",
        description=(
            "OTEL trace id (32 hex characters), as an alternative to 'entity_id' when "
            "annotating a Trace. For a caller that produced the trace and never saw the "
            "span row id it was stored under"
        ),
    )
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

    @model_validator(mode="after")
    def _one_way_of_naming_the_parent(self) -> "AnnotationCreate":
        """Exactly one parent address, and the hex only for a trace.

        A 32-character hex string also parses as a UUID, so a trace id sent as
        ``entity_id`` is accepted and then matches no row -- a silent miss
        rather than an error. Keeping the two in separate fields is what makes
        the wrong one impossible to send by accident.
        """
        if self.trace_id and self.entity_id:
            raise ValueError("Send entity_id or trace_id, not both")
        if not self.trace_id and not self.entity_id:
            raise ValueError("entity_id is required, or trace_id when annotating a Trace")
        if self.trace_id and self.entity_type != EntityType.TRACE.value:
            raise ValueError(
                f"trace_id names a Trace, but entity_type is '{self.entity_type}'. "
                f"Use entity_id for a {self.entity_type}"
            )
        return self


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
    # Set when the annotated entity is a metric's tuning case, which is reached
    # through the metric rather than through its test set.
    metric_id: Optional[UUID] = None


class AnnotationDetail(Annotation):
    context: Optional[AnnotationContext] = None

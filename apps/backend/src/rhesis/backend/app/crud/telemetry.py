"""CRUD operations for OpenTelemetry traces and spans.

Import the functions directly::

    from rhesis.backend.app.crud.telemetry import query_traces
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, NamedTuple, Optional, Union
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import TestExecutionContext
from rhesis.backend.app.schemas.telemetry import (
    OTELSpanCreate,
    StatusCode,
    TraceSource,
    TraceType,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include, resolve_chain

logger = logging.getLogger(__name__)


class TraceRow(NamedTuple):
    """A single row returned by query_traces.

    Using a NamedTuple instead of a plain tuple so callers can access fields
    by name (row.trace, row.span_count, row.total) instead of by index.
    """

    trace: models.Trace
    span_count: int
    total: int
    tags_count: int
    comments_count: int


# ============================================================================
# Trace CRUD Operations (OpenTelemetry Traces)
# ============================================================================


def create_trace_spans(
    db: Session,
    spans: List[OTELSpanCreate],
    organization_id: str,
) -> List[models.Trace]:
    """
    Create multiple trace spans in the database.

    Args:
        db: Database session
        spans: List of span schemas to create
        organization_id: Organization ID for multi-tenancy

    Returns:
        List of created Trace models

    Raises:
        Exception: If database operation fails
    """
    from uuid import UUID as _UUID

    def _safe_uuid(value: str | None, field_name: str) -> _UUID | None:
        if not value:
            return None
        try:
            return _UUID(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid UUID in test context {field_name}: {value}")
            return None

    trace_models = []

    for span in spans:
        duration_ms = (span.end_time - span.start_time).total_seconds() * 1000

        test_run_id = span.attributes.get("rhesis.test.run_id")
        test_result_id = span.attributes.get("rhesis.test.result_id")
        test_id = span.attributes.get("rhesis.test.id")

        trace_model = models.Trace(
            id=uuid.uuid4(),
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            project_id=span.project_id,
            organization_id=organization_id,
            environment=span.environment,
            conversation_id=span.conversation_id,
            span_name=span.span_name,
            span_kind=span.span_kind.value,
            start_time=span.start_time,
            end_time=span.end_time,
            duration_ms=duration_ms,
            status_code=span.status_code.value,
            status_message=span.status_message,
            attributes=span.attributes,
            events=[event.model_dump(mode="json") for event in span.events],
            links=[link.model_dump(mode="json") for link in span.links],
            resource=span.resource,
            test_run_id=_safe_uuid(test_run_id, "test_run_id"),
            test_result_id=_safe_uuid(test_result_id, "test_result_id"),
            test_id=_safe_uuid(test_id, "test_id"),
        )

        db.add(trace_model)
        trace_models.append(trace_model)

    prev_expire = db.expire_on_commit
    try:
        db.expire_on_commit = False
        db.commit()
        return trace_models
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create trace spans: {e}")
        raise
    finally:
        db.expire_on_commit = prev_expire


def get_trace_by_db_id(
    db: Session,
    trace_db_id: str,
    organization_id: str,
) -> Optional[models.Trace]:
    """Get a single trace span row by its database UUID.

    Raises ``ItemDeletedException`` for a soft-deleted trace.
    """
    from rhesis.backend.app.utils.crud_utils import get_item_detail

    return get_item_detail(db, models.Trace, UUID(trace_db_id), organization_id=organization_id)


def get_trace_by_id(
    db: Session,
    trace_id: str,
    project_id: str,
    organization_id: str,
    eager_load: Optional[List[str]] = None,
) -> List[models.Trace]:
    """
    Get all spans for a trace ID with optional eager loading.

    Args:
        db: Database session
        trace_id: OpenTelemetry trace ID
        project_id: Project ID for access control
        organization_id: Organization ID for multi-tenant security
        eager_load: Optional list of relationship names to eager load. Each
            entry may be a single name ("test_result") or a dotted chain
            ("test_result.test_configuration.endpoint") to eager-load a
            nested relationship in the same query.

    Returns:
        List of Trace models ordered by start_time
    """
    from uuid import UUID

    # Convert organization_id to UUID
    org_uuid = UUID(organization_id)

    builder = QueryBuilder(db, models.Trace).with_custom_filter(
        lambda q: q.filter(
            and_(
                models.Trace.trace_id == trace_id,
                models.Trace.project_id == project_id,
                models.Trace.organization_id == org_uuid,
            )
        )
    )

    # Add eager loading if specified
    if eager_load:
        options = [
            include(*resolve_chain(models.Trace, relationship.split(".")))
            for relationship in eager_load
        ]
        builder = builder.with_related(*options)

    return builder.with_sorting(sort_by="start_time").all()


def get_trace_id_for_conversation(
    db: Session,
    conversation_id: str,
    project_id: str,
    organization_id: str,
) -> Optional[str]:
    """
    Get the trace_id associated with a conversation.

    Looks up the earliest trace for the given conversation_id
    to reuse the same trace_id across all turns.

    Args:
        db: Database session
        conversation_id: The conversation identifier
        project_id: Project ID for access control
        organization_id: Organization ID for multi-tenant security

    Returns:
        The trace_id string, or None if no trace exists for this conversation
    """
    from uuid import UUID

    org_uuid = UUID(organization_id)

    result = (
        db.query(models.Trace.trace_id)
        .filter(
            and_(
                models.Trace.conversation_id == conversation_id,
                models.Trace.project_id == project_id,
                models.Trace.organization_id == org_uuid,
            )
        )
        .order_by(models.Trace.created_at)
        .limit(1)
        .first()
    )

    return result[0] if result else None


def _escape_like_pattern(term: str) -> str:
    """Escape SQL LIKE wildcards in user-provided search text."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_trace_search_conditions(pattern: str):
    """Case-insensitive substring match across common trace text fields."""
    from rhesis.backend.app.services.invokers.tracing import EndpointAttributes

    attrs = models.Trace.attributes

    esc = "\\"
    return or_(
        models.Trace.trace_id.ilike(pattern, escape=esc),
        models.Trace.span_name.ilike(pattern, escape=esc),
        models.Trace.status_message.ilike(pattern, escape=esc),
        attrs[EndpointAttributes.ENDPOINT_NAME].as_string().ilike(pattern, escape=esc),
        attrs[EndpointAttributes.ENDPOINT_URL].as_string().ilike(pattern, escape=esc),
        attrs[EndpointAttributes.CONVERSATION_INPUT].as_string().ilike(pattern, escape=esc),
        attrs[EndpointAttributes.CONVERSATION_OUTPUT].as_string().ilike(pattern, escape=esc),
        attrs[EndpointAttributes.RESPONSE_OUTPUT_PREVIEW].as_string().ilike(pattern, escape=esc),
    )


def query_traces(
    db: Session,
    organization_id: str,
    project_id: Optional[str] = None,
    endpoint_id: Optional[str] = None,
    root_spans_only: bool = True,
    trace_source: TraceSource = TraceSource.ALL,
    trace_type: TraceType = TraceType.ALL,
    environment: Optional[str] = None,
    search: Optional[str] = None,
    span_name: Optional[str] = None,
    status_code: Optional[Union[str, "StatusCode"]] = None,
    start_time_after: Optional[datetime] = None,
    start_time_before: Optional[datetime] = None,
    duration_min_ms: Optional[float] = None,
    duration_max_ms: Optional[float] = None,
    test_run_id: Optional[str] = None,
    test_result_id: Optional[str] = None,
    test_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    trace_metrics_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[TraceRow]:
    """
    Query traces with filters and eager load nested relationships.

    Returns a list of TraceRow named tuples, each containing:
      - trace:      the Trace ORM object
      - span_count: number of spans belonging to this trace
      - total:      total matching rows *before* LIMIT/OFFSET (for pagination)

    The total count is computed via a SQL window function (COUNT(*) OVER())
    inside the same query, so callers don't need a separate count query.

    When root_spans_only=True, conversation traces that share a trace_id
    across multiple turns are deduplicated — only the latest turn's root
    span is returned.

    Raises:
        HTTPException: 400 if any UUID parameter is malformed
    """
    from uuid import UUID

    from fastapi import HTTPException
    from sqlalchemy.orm import aliased, joinedload

    def validate_uuid_param(value: Optional[str], param_name: str) -> Optional[UUID]:
        """Validate and convert UUID string, raising HTTPException if invalid."""
        if not value:
            return None
        try:
            return UUID(value)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400, detail=f"Invalid UUID format for {param_name}: {value}"
            )

    # Convert organization_id to UUID
    org_uuid = UUID(organization_id)

    # -- Column 1: the Trace object itself (ORM model)
    # -- Column 2: span_count — how many spans share this trace_id
    #    Computed as a correlated subquery so we get it in one round-trip.
    InnerTrace = aliased(models.Trace)
    span_count_col = (
        select(func.count(InnerTrace.id))
        .where(
            and_(
                InnerTrace.trace_id == models.Trace.trace_id,
                InnerTrace.organization_id == org_uuid,
            )
        )
        .scalar_subquery()
    )

    # -- Column 3: total — total matching rows *before* LIMIT/OFFSET
    #    Uses a window function so pagination total comes from the same query.
    total_col = func.count().over().label("total_count")

    # -- Columns 4/5: tags_count/comments_count — correlated counts, same
    #    style as span_count_col, so the list view doesn't need to eager-load
    #    the full tag/comment rows just to know how many there are.
    tags_count_col = (
        select(func.count(models.TaggedItem.id))
        .where(
            and_(
                models.TaggedItem.entity_id == models.Trace.id,
                models.TaggedItem.entity_type == models.Trace.__name__,
            )
        )
        .scalar_subquery()
    )
    comments_count_col = (
        select(func.count(models.Comment.id))
        .where(
            and_(
                models.Comment.entity_id == models.Trace.id,
                models.Comment.entity_type == models.Trace.__name__,
                models.Comment.deleted_at.is_(None),
            )
        )
        .scalar_subquery()
    )

    query = (
        db.query(models.Trace, span_count_col, total_col, tags_count_col, comments_count_col)
        .filter(models.Trace.organization_id == org_uuid)
        .options(
            joinedload(models.Trace.test_result)
            .joinedload(models.TestResult.test_configuration)
            .joinedload(models.TestConfiguration.endpoint),
            joinedload(models.Trace.trace_metrics_status),
        )
    )

    if root_spans_only:
        query = query.filter(models.Trace.parent_span_id.is_(None))

        # Deduplicate by trace_id.
        #
        # Why this is needed: in multi-turn conversations, each turn produces
        # its own root span, but they all share the same trace_id. Without
        # dedup, the list would show the same trace once per turn.
        #
        # How it works: DISTINCT ON (trace_id) keeps one row per trace_id —
        # the one with the latest start_time (most recent turn). The result
        # is a set of row IDs that the outer query filters against.
        #
        # The subquery must include the same scoping filters as the outer
        # query (at minimum project_id) so DISTINCT ON picks a row that
        # the outer query can actually see.  Without this, a trace_id
        # shared across projects could cause the selected row to be
        # filtered out, making the trace disappear from results.
        dedup_filters = [
            models.Trace.parent_span_id.is_(None),
            models.Trace.organization_id == org_uuid,
        ]
        if project_id:
            dedup_filters.append(models.Trace.project_id == project_id)

        latest_root_per_trace = (
            db.query(models.Trace.id)
            .filter(*dedup_filters)
            .distinct(models.Trace.trace_id)
            .order_by(models.Trace.trace_id, desc(models.Trace.start_time))
            .subquery()
        )
        query = query.filter(models.Trace.id.in_(select(latest_root_per_trace.c.id)))

    # Filter by trace source
    if trace_source == TraceSource.TEST:
        query = query.filter(models.Trace.test_run_id.isnot(None))
    elif trace_source == TraceSource.OPERATION:
        query = query.filter(models.Trace.test_run_id.is_(None))
    # If TraceSource.ALL, no additional filter needed

    # Add project_id filter only if specified
    if project_id:
        query = query.filter(models.Trace.project_id == project_id)

    # Add endpoint_id filter - join through TestResult -> TestConfiguration -> Endpoint
    if endpoint_id:
        endpoint_uuid = validate_uuid_param(endpoint_id, "endpoint_id")
        if endpoint_uuid:
            query = (
                query.join(models.TestResult, models.Trace.test_result_id == models.TestResult.id)
                .join(
                    models.TestConfiguration,
                    models.TestResult.test_configuration_id == models.TestConfiguration.id,
                )
                .join(
                    models.Endpoint,
                    models.TestConfiguration.endpoint_id == models.Endpoint.id,
                )
                .filter(models.Endpoint.id == endpoint_uuid)
            )

    if environment:
        query = query.filter(models.Trace.environment == environment)

    if search and search.strip():
        pattern = f"%{_escape_like_pattern(search.strip())}%"
        search_filters = [
            models.Trace.organization_id == org_uuid,
            _build_trace_search_conditions(pattern),
        ]
        if project_id:
            search_filters.append(models.Trace.project_id == project_id)

        matching_trace_ids = (
            db.query(models.Trace.trace_id).filter(*search_filters).distinct().subquery()
        )
        query = query.filter(models.Trace.trace_id.in_(select(matching_trace_ids.c.trace_id)))

    elif span_name:
        query = query.filter(models.Trace.span_name == span_name)

    if status_code:
        # Convert enum to value if needed
        status_value = status_code.value if isinstance(status_code, Enum) else status_code
        query = query.filter(models.Trace.status_code == status_value)

    if start_time_after:
        query = query.filter(models.Trace.start_time >= start_time_after)

    if start_time_before:
        query = query.filter(models.Trace.start_time <= start_time_before)

    if duration_min_ms is not None:
        query = query.filter(models.Trace.duration_ms >= duration_min_ms)

    if duration_max_ms is not None:
        query = query.filter(models.Trace.duration_ms <= duration_max_ms)

    # Test execution filters - validate UUIDs before using
    test_run_uuid = validate_uuid_param(test_run_id, "test_run_id")
    if test_run_uuid:
        query = query.filter(models.Trace.test_run_id == test_run_uuid)

    test_result_uuid = validate_uuid_param(test_result_id, "test_result_id")
    if test_result_uuid:
        query = query.filter(models.Trace.test_result_id == test_result_uuid)

    test_id_uuid = validate_uuid_param(test_id, "test_id")
    if test_id_uuid:
        query = query.filter(models.Trace.test_id == test_id_uuid)

    if conversation_id:
        query = query.filter(models.Trace.conversation_id == conversation_id)

    # Trace type filter (single-turn vs multi-turn)
    if trace_type == TraceType.MULTI_TURN:
        query = query.filter(models.Trace.conversation_id.isnot(None))
    elif trace_type == TraceType.SINGLE_TURN:
        query = query.filter(models.Trace.conversation_id.is_(None))

    # Trace metrics evaluation status filter (Pass / Fail / Error)
    # Uses an IN subquery instead of a scalar to handle orgs where the same
    # status name exists for multiple entity types (e.g. multiple "Error" rows).
    if trace_metrics_status:
        matching_status_ids = select(models.Status.id).where(
            models.Status.name == trace_metrics_status,
            models.Status.organization_id == org_uuid,
        )
        query = query.filter(models.Trace.trace_metrics_status_id.in_(matching_status_ids))

    results = query.order_by(desc(models.Trace.start_time)).limit(limit).offset(offset).all()
    return [
        TraceRow(trace=r[0], span_count=r[1], total=r[2], tags_count=r[3], comments_count=r[4])
        for r in results
    ]


def get_unprocessed_traces(
    db: Session,
    limit: int = 100,
) -> List[models.Trace]:
    """
    Get traces that haven't been processed yet.

    Used by background workers to find traces needing enrichment.

    Args:
        db: Database session
        limit: Maximum traces to return

    Returns:
        List of unprocessed Trace models
    """
    return (
        db.query(models.Trace)
        .filter(models.Trace.processed_at.is_(None))
        .order_by(models.Trace.created_at)
        .limit(limit)
        .all()
    )


def mark_trace_processed(
    db: Session,
    trace_id: str,
    enriched_data: dict,
) -> int:
    """
    Mark all spans in a trace as processed.

    Args:
        db: Database session
        trace_id: OpenTelemetry trace ID
        enriched_data: Enriched attributes to store

    Returns:
        Number of spans updated
    """
    result = (
        db.query(models.Trace)
        .filter(models.Trace.trace_id == trace_id)
        .update(
            {
                "processed_at": datetime.now(timezone.utc),
                "enriched_data": enriched_data,
                "updated_at": datetime.now(timezone.utc),
            }
        )
    )

    db.commit()
    return result


def update_traces_with_test_result_id(
    db: Session,
    test_run_id: str,
    test_id: str,
    test_configuration_id: str,
    test_result_id: str,
    organization_id: str,
) -> int:
    """
    Update test_result_id for all traces matching the test execution context.

    This links traces to their test result record after the test completes.
    Works for all trace sources:
    - SDK automatic tracing (spans sent from client)
    - REST/WebSocket manual tracing (spans created by backend)

    Args:
        db: Database session
        test_run_id: Test run UUID string
        test_id: Test UUID string
        test_configuration_id: Test configuration UUID string
        test_result_id: Test result UUID string to set
        organization_id: Organization UUID string for multi-tenancy

    Returns:
        Number of spans updated
    """
    logger.info(
        f"[TRACE_LINKING] Starting trace linking for test_result_id={test_result_id}, "
        f"test_run_id={test_run_id}, test_id={test_id}, "
        f"test_configuration_id={test_configuration_id}, organization_id={organization_id}"
    )

    # Convert string UUIDs to UUID objects
    test_run_uuid = uuid.UUID(test_run_id)
    test_id_uuid = uuid.UUID(test_id)
    test_config_uuid = uuid.UUID(test_configuration_id)
    test_result_uuid = uuid.UUID(test_result_id)
    org_uuid = uuid.UUID(organization_id)

    # First, count how many traces match our criteria
    matching_traces = (
        db.query(models.Trace)
        .filter(
            models.Trace.test_run_id == test_run_uuid,
            models.Trace.test_id == test_id_uuid,
            models.Trace.organization_id == org_uuid,
            models.Trace.attributes[
                TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID
            ].astext
            == str(test_config_uuid),
            models.Trace.test_result_id.is_(None),
        )
        .all()
    )

    logger.debug(
        f"[TRACE_LINKING] Found {len(matching_traces)} traces matching criteria "
        f"(test_run_id={test_run_uuid}, test_id={test_id_uuid}, "
        f"test_configuration_id={test_config_uuid}, organization_id={org_uuid})"
    )

    if len(matching_traces) > 0:
        logger.debug(f"[TRACE_LINKING] Sample trace attributes: {matching_traces[0].attributes}")
    else:
        # Check if there are ANY traces for this test_run
        all_traces_for_run = (
            db.query(models.Trace).filter(models.Trace.test_run_id == test_run_uuid).all()
        )
        logger.warning(
            f"[TRACE_LINKING] No matching traces found! "
            f"Total traces for test_run_id={test_run_uuid}: {len(all_traces_for_run)}"
        )
        if len(all_traces_for_run) > 0:
            logger.debug(
                f"[TRACE_LINKING] Sample trace from run - "
                f"test_id: {all_traces_for_run[0].test_id}, "
                f"test_result_id: {all_traces_for_run[0].test_result_id}, "
                f"attributes: {all_traces_for_run[0].attributes}"
            )

    result = (
        db.query(models.Trace)
        .filter(
            models.Trace.test_run_id == test_run_uuid,
            models.Trace.test_id == test_id_uuid,
            models.Trace.organization_id == org_uuid,
            # Also check attributes for test_configuration_id since it's stored there
            models.Trace.attributes[
                TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID
            ].astext
            == str(test_config_uuid),
            # Only update if test_result_id is NULL (idempotent)
            models.Trace.test_result_id.is_(None),
        )
        .update(
            {
                "test_result_id": test_result_uuid,
                "updated_at": datetime.now(timezone.utc),
            },
            synchronize_session=False,  # More efficient for bulk updates
        )
    )

    # Flush to make changes visible within the current transaction
    # The context manager (get_db_with_tenant_variables) handles the final commit
    db.flush()

    logger.info(f"[TRACE_LINKING] Updated {result} traces with test_result_id={test_result_id}")

    return result


def update_conversation_id_for_trace(
    db: Session,
    trace_id: str,
    conversation_id: str,
    organization_id: str,
) -> int:
    """
    Retroactively set conversation_id on all spans of a trace.

    Used when the first turn of a conversation has no conversation_id
    at invocation time (stateful endpoints generate the ID in their
    response). After the response is processed, this function stamps
    the discovered conversation_id onto the already-stored trace spans.

    Only updates spans where conversation_id IS NULL to avoid
    overwriting intentionally set values.

    Returns the number of rows updated.
    """
    org_uuid = UUID(organization_id)

    count = (
        db.query(models.Trace)
        .filter(
            and_(
                models.Trace.trace_id == trace_id,
                models.Trace.organization_id == org_uuid,
                models.Trace.conversation_id.is_(None),
            )
        )
        .update(
            {
                models.Trace.conversation_id: conversation_id,
                models.Trace.updated_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )

    db.flush()

    logger.debug(
        f"[TRACE_LINKING] Updated {count} spans with "
        f"conversation_id={conversation_id} for trace_id={trace_id}"
    )

    return count


# ---------------------------------------------------------------
# Trace metrics CRUD helpers
# ---------------------------------------------------------------


def update_trace_turn_metrics(
    db: Session,
    span_id: str,
    turn_metrics: dict,
    status_id: Optional[str] = None,
    execution: Optional[str] = None,
    verdict: Optional[str] = None,
    processed_at: Optional[datetime] = None,
) -> int:
    """Update turn-level trace metrics on a single span row.

    Merges turn_metrics into trace_metrics.turn_metrics without
    overwriting conversation_metrics if already present.

    ``execution``/``verdict`` are the source of truth (app/outcomes.py) and
    are written together with the legacy ``status_id``; see
    jobs/telemetry/evaluate.py's _derive_outcome, which produces all three
    from one classification.
    """
    span = db.query(models.Trace).filter(models.Trace.id == span_id).first()
    if not span:
        return 0

    existing = span.trace_metrics or {}
    existing["turn_metrics"] = turn_metrics
    now = processed_at or datetime.now(timezone.utc)

    update_values: Dict[str, Any] = {
        "trace_metrics": existing,
        "trace_metrics_processed_at": now,
        "updated_at": datetime.now(timezone.utc),
    }
    if status_id is not None:
        update_values["trace_metrics_status_id"] = status_id
    if execution is not None:
        # verdict is written unconditionally alongside execution: the
        # ck_trace_verdict_requires_ok constraint means leaving a stale
        # verdict behind when execution moves off 'ok' would fail the write.
        update_values["execution"] = execution
        update_values["verdict"] = verdict

    result = db.query(models.Trace).filter(models.Trace.id == span_id).update(update_values)
    db.commit()
    return result


def update_trace_conversation_metrics(
    db: Session,
    trace_id: str,
    conversation_metrics: dict,
    status_id: Optional[str] = None,
    execution: Optional[str] = None,
    verdict: Optional[str] = None,
    processed_at: Optional[datetime] = None,
) -> int:
    """Update conversation-level trace metrics on all spans sharing a trace_id.

    Writes conversation_metrics into trace_metrics.conversation_metrics on
    every span row, re-derives status from combined turn + conversation results.
    """
    from sqlalchemy.orm.attributes import flag_modified

    spans = db.query(models.Trace).filter(models.Trace.trace_id == trace_id).all()
    if not spans:
        return 0

    now = processed_at or datetime.now(timezone.utc)
    count = 0
    for span in spans:
        existing = span.trace_metrics or {}
        # Important: copy the dict so SQLAlchemy detects the change, or use flag_modified
        new_metrics = dict(existing)
        new_metrics["conversation_metrics"] = conversation_metrics
        span.trace_metrics = new_metrics

        # Explicitly flag the JSON column as modified
        flag_modified(span, "trace_metrics")

        span.trace_metrics_processed_at = now
        span.updated_at = datetime.now(timezone.utc)
        if status_id is not None:
            span.trace_metrics_status_id = status_id
        if execution is not None:
            # Paired write -- see update_trace_turn_metrics.
            span.execution = execution
            span.verdict = verdict
        count += 1

    db.commit()
    return count


def get_trace_metrics_aggregated(
    db: Session,
    organization_id: str,
    project_id: str,
    environment: Optional[str] = None,
    start_time_after: Optional[datetime] = None,
    start_time_before: Optional[datetime] = None,
) -> dict:
    """Compute trace metrics using SQL-level aggregation.

    Uses PostgreSQL aggregate functions (COUNT, SUM, AVG, percentile_cont)
    to avoid loading large result sets into Python memory.
    """
    from uuid import UUID

    from sqlalchemy import case, literal_column
    from sqlalchemy.sql import functions as sqlfunc

    from rhesis.backend.app.constants import AISpanAttributes, EnrichedDataKeys

    T = models.Trace

    filters = [
        T.organization_id == UUID(organization_id),
        T.project_id == UUID(project_id),
        T.deleted_at.is_(None),
    ]
    if environment:
        filters.append(T.environment == environment)
    if start_time_after:
        filters.append(T.start_time >= start_time_after)
    if start_time_before:
        filters.append(T.start_time <= start_time_before)

    base = db.query(T).filter(*filters).subquery()

    # JSONB extraction expressions for tokens and costs
    tokens_expr = base.c.attributes[AISpanAttributes.TOKENS_TOTAL].as_float()
    cost_expr = base.c.enriched_data[EnrichedDataKeys.COSTS][
        EnrichedDataKeys.TOTAL_COST_USD
    ].as_float()

    agg = db.query(
        func.count(func.distinct(base.c.trace_id)).label("total_traces"),
        func.count(base.c.id).label("total_spans"),
        func.coalesce(func.sum(tokens_expr), 0).label("total_tokens"),
        func.coalesce(func.sum(cost_expr), 0).label("total_cost_usd"),
        func.count(case((base.c.status_code == "ERROR", 1))).label("error_count"),
        func.coalesce(func.avg(base.c.duration_ms), 0).label("avg_duration_ms"),
        func.coalesce(sqlfunc.percentile_cont(0.5).within_group(base.c.duration_ms), 0).label(
            "p50_duration_ms"
        ),
        func.coalesce(sqlfunc.percentile_cont(0.95).within_group(base.c.duration_ms), 0).label(
            "p95_duration_ms"
        ),
        func.coalesce(sqlfunc.percentile_cont(0.99).within_group(base.c.duration_ms), 0).label(
            "p99_duration_ms"
        ),
    ).one()

    total_spans = agg.total_spans or 0
    error_count = agg.error_count or 0

    # Operation breakdown as a separate grouped query
    op_type_expr = func.coalesce(
        base.c.attributes[AISpanAttributes.OPERATION_TYPE].as_string(),
        literal_column("'unknown'"),
    )
    op_rows = (
        db.query(
            op_type_expr.label("op_type"),
            func.count(base.c.id).label("cnt"),
        )
        .group_by(op_type_expr)
        .all()
    )

    return {
        "total_traces": agg.total_traces or 0,
        "total_spans": total_spans,
        "total_tokens": int(agg.total_tokens or 0),
        "total_cost_usd": round(float(agg.total_cost_usd or 0), 6),
        "error_rate": round(error_count / total_spans, 4) if total_spans else 0,
        "avg_duration_ms": round(float(agg.avg_duration_ms or 0), 2),
        "p50_duration_ms": round(float(agg.p50_duration_ms or 0), 2),
        "p95_duration_ms": round(float(agg.p95_duration_ms or 0), 2),
        "p99_duration_ms": round(float(agg.p99_duration_ms or 0), 2),
        "operation_breakdown": {row.op_type: row.cnt for row in op_rows},
    }

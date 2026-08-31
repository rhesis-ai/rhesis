"""CRUD operations for test runs.

``get_test_run`` and ``get_test_runs`` both push ``_defer_endpoint_last_token`` through
``with_custom_filter``. The eager chain down to ``TestConfiguration.endpoint`` would
otherwise pull ``Endpoint.last_token`` -- a large encrypted OAuth token that no test run
response ever returns -- into every row.

``get_test_run_metrics`` extracts metric names with Postgres' ``jsonb_object_keys()``
rather than loading ``TestResult.test_metrics`` and deduplicating in Python, so the JSONB
payloads stay in the database.

``create_test_run`` generates a memorable name when the caller leaves it blank, and falls
back to a timestamp-based one if generation fails. ``delete_test_run`` is a soft delete;
the cascade to test results is driven by ``config/cascade_config.py`` inside
``delete_item``.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    bulk_delete_by_ids,
    create_item,
    delete_item,
    get_item_detail,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.name_generator import generate_memorable_name
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

logger = logging.getLogger(__name__)


# Relationships loaded for TestRun detail responses. Matches schemas.TestRunDetail.
# assignee/owner/organization/experiment/project (TestRun's own top-level fields) are
# unused, excluded; the nested test_configuration.endpoint.project chain below is a
# separate, still-used field.
_TEST_RUN_RELATED_FIELDS = (
    include(models.TestRun.status),
    include(models.TestRun.user),
    include(models.TestRun.test_configuration, models.TestConfiguration.endpoint),
    include(
        models.TestRun.test_configuration,
        models.TestConfiguration.endpoint,
        models.Endpoint.project,
    ),
    include(models.TestRun.test_configuration, models.TestConfiguration.test_set),
    include(
        models.TestRun.test_configuration,
        models.TestConfiguration.test_set,
        models.TestSet.test_set_type,
    ),
)


def _defer_endpoint_last_token(q):
    """Defer Endpoint.last_token — a large encrypted OAuth token never returned in responses."""
    return q.options(
        joinedload(models.TestRun.test_configuration)
        .joinedload(models.TestConfiguration.endpoint)
        .defer(models.Endpoint.last_token)
    )


def get_test_run(
    db: Session,
    test_run_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestRun]:
    """Get test_run with relationships eagerly loaded (including nested chains)."""
    return get_item_detail(
        db,
        models.TestRun,
        test_run_id,
        organization_id,
        user_id,
        related_fields=_TEST_RUN_RELATED_FIELDS,
        extra_filter=_defer_endpoint_last_token,
    )


def _test_run_experiment_filter(
    db: Session,
    experiment_id: str | None,
    parameter_version: str | None,
    has_experiment: bool | None,
    has_reviews: bool | None,
    organization_id: str | None,
):
    """Build the experiment/parameter/review row-selection filter for get_test_runs.

    A row-selection filter (like ``with_odata_filter``), not a loader option --
    must run on the phase-1 id query so the right page of ids is picked in the
    first place; see get_items_detail's ``extra_filter`` vs ``hydrate_filter``.
    """

    def _filter(q):
        if experiment_id:
            q = q.filter(models.TestRun.experiment_id == experiment_id)
        if parameter_version:
            q = q.filter(
                models.TestRun.attributes["parameter_version"].astext == str(parameter_version)
            )
        if has_experiment is True:
            q = q.filter(models.TestRun.experiment_id.isnot(None))
        elif has_experiment is False:
            q = q.filter(models.TestRun.experiment_id.is_(None))
        if has_reviews is not None:
            from uuid import UUID

            from sqlalchemy import func

            exists_filters = [
                models.TestResult.test_run_id == models.TestRun.id,
                models.TestResult.test_reviews.isnot(None),
                func.jsonb_typeof(models.TestResult.test_reviews["reviews"]) == "array",
                func.coalesce(
                    func.jsonb_array_length(models.TestResult.test_reviews["reviews"]),
                    0,
                )
                > 0,
            ]
            if organization_id:
                exists_filters.append(models.TestResult.organization_id == UUID(organization_id))

            reviewed_result_exists = db.query(models.TestResult.id).filter(*exists_filters).exists()
            q = q.filter(reviewed_result_exists if has_reviews else ~reviewed_result_exists)
        return q

    return _filter


def get_test_runs(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    experiment_id: str | None = None,
    parameter_version: str | None = None,
    has_experiment: bool | None = None,
    has_reviews: bool | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.TestRun]:
    return get_items_detail(
        db,
        models.TestRun,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_TEST_RUN_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
        extra_filter=_test_run_experiment_filter(
            db, experiment_id, parameter_version, has_experiment, has_reviews, organization_id
        ),
        hydrate_filter=_defer_endpoint_last_token,
    )


def get_test_run_requirements(
    db: Session, test_run_id: uuid.UUID, organization_id: str | None = None
) -> List[models.Requirement]:
    """Get requirements that have test results for a test run, filtered by organization."""
    # Verify the test run exists (UUID lookup is safe)
    test_run = get_test_run(db, test_run_id, organization_id=organization_id)
    if not test_run:
        raise ValueError(f"Test run with id {test_run_id} not found")

    # Get unique requirement IDs from tests that have results in this test run
    # SECURITY: Add organization filtering
    requirement_ids_query = (
        db.query(models.Test.requirement_id)
        .join(models.TestResult, models.Test.id == models.TestResult.test_id)
        .filter(
            models.TestResult.test_run_id == test_run_id,
            models.Test.requirement_id.isnot(None),  # Only tests that have a requirement
        )
    )

    # Apply organization filtering (SECURITY CRITICAL)
    if organization_id:
        from uuid import UUID

        requirement_ids_query = requirement_ids_query.filter(
            models.Test.organization_id == UUID(organization_id)
        )

    requirement_ids_query = requirement_ids_query.distinct()

    requirement_ids = [row[0] for row in requirement_ids_query.all()]

    if not requirement_ids:
        return []

    # Get the actual requirement objects with proper filtering
    return (
        QueryBuilder(db, models.Requirement)
        .with_related(include(models.Requirement.user))
        .with_visibility_filter()
        .with_custom_filter(lambda q: q.filter(models.Requirement.id.in_(requirement_ids)))
        .with_sorting("name", "asc")
        .all()
    )


def get_test_run_metrics(
    db: Session,
    test_run_id: uuid.UUID,
    organization_id: uuid.UUID | str | None = None,
) -> List[str]:
    """Get distinct metric names actually evaluated in a specific test run.

    Uses jsonb_object_keys() in Postgres to extract and deduplicate metric
    names at the database level, avoiding transferring full JSONB payloads
    to the application layer.
    """
    metric_key = func.jsonb_object_keys(models.TestResult.test_metrics["metrics"]).label(
        "metric_name"
    )

    query = db.query(metric_key).filter(
        models.TestResult.test_run_id == test_run_id,
        models.TestResult.test_metrics.isnot(None),
        func.jsonb_typeof(models.TestResult.test_metrics["metrics"]) == "object",
    )

    if organization_id:
        try:
            org_uuid = (
                organization_id
                if isinstance(organization_id, uuid.UUID)
                else uuid.UUID(str(organization_id))
            )
        except ValueError:
            return []
        query = query.filter(models.TestResult.organization_id == org_uuid)

    return sorted({name for (name,) in query.distinct().all()})


def create_test_run(
    db: Session,
    test_run: schemas.TestRunCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.TestRun:
    """Create a new test run with automatic name generation if no name is provided"""

    # If no name is provided or it's empty, generate a memorable one
    if not test_run.name or not test_run.name.strip():
        # Get organization_id for scoping uniqueness
        organization_id = test_run.organization_id
        if not organization_id:
            # Try to get from session context if not explicitly provided
            from rhesis.backend.app.utils.crud_utils import get_current_organization_id

            organization_id = get_current_organization_id(db)

        if organization_id:
            try:
                generated_name = generate_memorable_name(db, organization_id)
                logger.info(f"Generated memorable name for test run: {generated_name}")

                # Create a new TestRunCreate with the generated name
                test_run_dict = (
                    test_run.model_dump() if hasattr(test_run, "model_dump") else test_run.dict()
                )
                test_run_dict["name"] = generated_name
                test_run = schemas.TestRunCreate(**test_run_dict)
            except Exception as e:
                logger.warning(f"Failed to generate memorable name: {e}. Using fallback.")
                # Fallback to a simple timestamp-based name
                import time

                timestamp = int(time.time())
                test_run_dict = (
                    test_run.model_dump() if hasattr(test_run, "model_dump") else test_run.dict()
                )
                test_run_dict["name"] = f"test-run-{timestamp}"
                test_run = schemas.TestRunCreate(**test_run_dict)
        else:
            logger.warning("No organization_id available for test run name generation")

    return create_item(
        db, models.TestRun, test_run, organization_id=organization_id, user_id=user_id
    )


def update_test_run(
    db: Session,
    test_run_id: uuid.UUID,
    test_run: schemas.TestRunUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestRun]:
    """Update test_run."""
    return update_item(db, models.TestRun, test_run_id, test_run, organization_id, user_id)


def delete_test_run(
    db: Session, test_run_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.TestRun]:
    """
    Soft delete a test run.

    Automatically cascades to all associated test results based on configuration
    in config/cascade_config.py. Uses efficient bulk UPDATE for cascade operations.

    This operation is fully transactional - either all entities are soft deleted
    or none are (in case of error, changes are rolled back).

    Args:
        db: Database session
        test_run_id: ID of the test run to delete
        organization_id: Organization ID for tenant context
        user_id: User ID for tenant context

    Returns:
        The soft-deleted test run or None if not found

    Raises:
        Exception: If any error occurs during deletion (triggers rollback)
    """
    # delete_item() automatically handles cascade based on cascade_config.py
    return delete_item(
        db, models.TestRun, test_run_id, organization_id=organization_id, user_id=user_id
    )


def bulk_delete_test_runs(
    db: Session,
    test_run_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """
    Soft delete multiple test runs in one transaction, enforcing the same
    owner-only rule as the single-item delete route: only the creator may
    delete their own test run. Ids that exist but belong to someone else are
    reported in "forbidden_ids" rather than silently skipped or deleted.
    """
    return bulk_delete_by_ids(
        db,
        models.TestRun,
        test_run_ids,
        organization_id=organization_id,
        user_id=user_id,
        owner_attr="user_id",
    )


def get_test_run_task_ids(
    db: Session,
    test_run_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[uuid.UUID, Tuple[Optional[str], Optional[str]]]:
    """Map ids in ``test_run_ids`` to (status_name, task_id).

    Used by the bulk-delete route to find active runs among the ones it's
    about to soft-delete, so their Celery task can be revoked -- same as the
    single-item delete route does per-run. Deciding which status counts as
    "active" is left to the caller (RunStatus lives in tasks/, which this
    module must not import -- see AGENTS.md's tasks-layout rule).

    Scoped to ``user_id``'s own runs, matching bulk_delete_test_runs's
    owner_attr check: the caller only ever consults this for ids that end up
    in "deleted_ids", so fetching runs that would land in "forbidden_ids"
    (visible in-org but not owned) would just be discarded work.
    """
    rows = (
        QueryBuilder(db, models.TestRun)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_related(include(models.TestRun.status))
        .with_custom_filter(lambda q: q.filter(models.TestRun.id.in_(test_run_ids)))
        .with_custom_filter(lambda q: q.filter(models.TestRun.user_id == user_id))
        .all()
    )
    return {
        row.id: (row.status.name if row.status else None, (row.attributes or {}).get("task_id"))
        for row in rows
    }


def get_ordered_tests_for_test_set(
    db: Session, test_set_id: uuid.UUID, organization_id: str | None = None
) -> List[Tuple[str, Optional[str], bool]]:
    """Return ``[(test_id, requirement_id, is_multi_turn)]`` for a test set, ordered by test id.

    Lean projection query (no ORM model hydration) used to snapshot the metric
    plan's ``test_order`` at dispatch time, as the fallback column list for a
    legacy test run with no stored plan, and (via ``is_multi_turn``) to apply
    the same single-turn/multi-turn scope filtering the execution path uses.
    """
    from rhesis.backend.app.constants import TestType
    from rhesis.backend.app.models.test import Test, test_test_set_association
    from rhesis.backend.app.models.type_lookup import TypeLookup

    query = (
        db.query(Test.id, Test.requirement_id, TypeLookup.type_value)
        .join(test_test_set_association, test_test_set_association.c.test_id == Test.id)
        .outerjoin(TypeLookup, Test.test_type_id == TypeLookup.id)
        .filter(
            test_test_set_association.c.test_set_id == test_set_id,
            Test.deleted_at.is_(None),
        )
    )
    if organization_id:
        query = query.filter(Test.organization_id == uuid.UUID(str(organization_id)))

    rows = query.order_by(Test.id).all()
    return [
        (
            str(test_id),
            str(requirement_id) if requirement_id else None,
            type_value == TestType.MULTI_TURN.value,
        )
        for test_id, requirement_id, type_value in rows
    ]


def get_review_count_for_run(
    db: Session, test_run_id: uuid.UUID, organization_id: str | None = None
) -> int:
    """Count distinct tests with at least one review recorded, for this run.

    A coarse presence count, not the detailed test-vs-metric /
    review-vs-correction breakdown ``BreakdownsDrawer`` computes lazily from
    full test result bodies -- this only answers "has anything been
    reviewed yet" for the KPI row, so it stays a single indexed-by-run
    aggregate instead of hydrating every result. Same JSONB presence
    predicate as ``_test_run_experiment_filter``'s ``has_reviews`` filter
    above.
    """
    query = db.query(func.count(func.distinct(models.TestResult.test_id))).filter(
        models.TestResult.test_run_id == test_run_id,
        models.TestResult.test_reviews.isnot(None),
        func.jsonb_typeof(models.TestResult.test_reviews["reviews"]) == "array",
        func.coalesce(func.jsonb_array_length(models.TestResult.test_reviews["reviews"]), 0) > 0,
    )
    if organization_id:
        query = query.filter(models.TestResult.organization_id == uuid.UUID(str(organization_id)))
    return query.scalar() or 0


def get_metric_verdicts_for_run(
    db: Session, test_run_id: uuid.UUID, organization_id: str | None = None
) -> List[Row]:
    """Return one row per (test, metric) evaluated in this run, from ``v_metric_stats``.

    Projects the five columns the verdict grid reads rather than hydrating
    ``MetricStatsView`` instances: the verdict-matrix endpoint is refetched
    on every coalesced progress tick, per connected client, and a large run
    is tens of thousands of rows -- ORM hydration there is pure overhead for
    values that are read once and encoded into a string.
    """
    query = db.query(
        models.MetricStatsView.test_id,
        models.MetricStatsView.requirement_id,
        models.MetricStatsView.metric_name,
        models.MetricStatsView.effective_success,
        models.MetricStatsView.has_override,
        models.MetricStatsView.created_at,
    ).filter(models.MetricStatsView.test_run_id == test_run_id)
    if organization_id:
        query = query.filter(
            models.MetricStatsView.organization_id == uuid.UUID(str(organization_id))
        )
    return query.all()


def get_test_outcomes_for_run(
    db: Session, test_run_id: uuid.UUID, organization_id: str | None = None
) -> Dict[str, str]:
    """Map ``test_id`` to its most recent result's outcome for this run.

    Reads ``v_test_result_stats.result`` directly: it now derives from
    ``test_result.execution``/``verdict`` (the outcome-model source of
    truth, see ``app/outcomes.py``) and distinguishes passed/failed/error/
    cancelled/pending on its own, so there is no synonym list left to run
    here.
    """
    query = db.query(
        models.TestResultStatsView.test_id,
        models.TestResultStatsView.result,
        models.TestResultStatsView.created_at,
    ).filter(models.TestResultStatsView.test_run_id == test_run_id)
    if organization_id:
        query = query.filter(
            models.TestResultStatsView.organization_id == uuid.UUID(str(organization_id))
        )
    rows = query.all()

    latest: Dict[str, Tuple[Any, str]] = {}
    for test_id, result, created_at in rows:
        key = str(test_id)
        if key not in latest or created_at > latest[key][0]:
            latest[key] = (created_at, result)

    return {test_id: result for test_id, (_, result) in latest.items()}

"""CRUD operations for test sets."""

import logging
import uuid
from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    bulk_delete_by_ids,
    create_item,
    delete_item,
    get_item_detail,
    update_item,
)
from rhesis.backend.app.utils.hidden_rows import exclude_metric_owned
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

logger = logging.getLogger(__name__)


def get_test_set(
    db: Session, test_set_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TestSet]:
    """
    Get a test set by its UUID, applying proper visibility filtering and organization scoping.

    Raises ``ItemDeletedException`` for a soft-deleted test set.
    """
    return get_item_detail(
        db, models.TestSet, test_set_id, organization_id=organization_id, user_id=user_id
    )


# Relationships serialized by TestSetDetailSchema. All many-to-one -- excludes
# collection relationships (prompts, tests, metrics, test_configurations)
# because those produce cartesian-product joins or lazy fan-out and none of
# these endpoints serialize them. comments/tasks/files/tags ARE serialized
# (via CountsMixin.counts / TagsMixin.tags) -- see with_default_derived_field_loads.
# license_type/owner/assignee/organization/project: unused, excluded.
_TEST_SET_RELATED_FIELDS = (
    include(models.TestSet.status),
    include(models.TestSet.test_set_type),
    include(models.TestSet.user),
)


def get_test_sets(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    has_runs: bool | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.TestSet]:
    """
    Get test sets with detail loading and proper filtering.
    Public test sets are visible regardless of organization.
    Organization filtering is applied when organization_id is provided.
    """
    query_builder = (
        QueryBuilder(db, models.TestSet)
        .with_related(*_TEST_SET_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)  # Apply organization filtering
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
    )

    # Add test runs filter if specified
    if has_runs is not None:

        def has_runs_filter(query):
            logger.info(f"Applying has_runs filter: {has_runs}")

            if has_runs:
                # Only test sets that have test runs
                filtered_query = (
                    query.join(models.TestConfiguration).join(models.TestRun).distinct()
                )
                logger.info("Applied filter for test sets WITH runs")
                return filtered_query
            else:
                # Only test sets that don't have test runs
                subquery_builder = QueryBuilder(db, models.TestSet).with_organization_filter(
                    organization_id
                )
                subquery = (
                    subquery_builder.build()
                    .join(models.TestConfiguration)
                    .join(models.TestRun)
                    .distinct()
                    .with_entities(models.TestSet.id)
                    .subquery()
                )
                filtered_query = query.filter(~models.TestSet.id.in_(subquery))
                logger.info("Applied filter for test sets WITHOUT runs")
                return filtered_query

        query_builder = query_builder.with_custom_filter(has_runs_filter)

    # Exclude explorer test sets (they use the dedicated /explorer API)
    # A metric's tuning test set is reachable only through its metric.
    return (
        query_builder.with_custom_filter(lambda q: q.filter(models.TestSet.explorer_row.is_(False)))
        .with_custom_filter(exclude_metric_owned(models.TestSet))
        .all()
    )


def create_test_set(
    db: Session, test_set: schemas.TestSetCreate, organization_id: str = None, user_id: str = None
) -> models.TestSet:
    """Create test_set."""
    return create_item(db, models.TestSet, test_set, organization_id, user_id)


def update_test_set(
    db: Session,
    test_set_id: uuid.UUID,
    test_set: schemas.TestSetUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TestSet]:
    """Update test_set."""
    return update_item(db, models.TestSet, test_set_id, test_set, organization_id, user_id)


def delete_test_set(
    db: Session, test_set_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.TestSet]:
    return delete_item(
        db, models.TestSet, test_set_id, organization_id=organization_id, user_id=user_id
    )


def get_test_set_by_nano_id_or_slug(
    db: Session, identifier: str, organization_id: str = None, user_id: str = None
) -> Optional[models.TestSet]:
    """
    Get a test set by its nano_id or slug, applying proper visibility filtering.

    Raises ``ItemDeletedException`` for a soft-deleted test set.
    """
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.TestSet)
        .with_deleted()
        .with_related(*_TEST_SET_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_custom_filter(
            lambda q: q.filter(
                (models.TestSet.nano_id == identifier) | (models.TestSet.slug == identifier)
            )
        )
        .first()
    )
    return _check_and_raise_if_deleted(item, models.TestSet, identifier, False)


def resolve_test_set(
    identifier: str, db: Session, organization_id: str = None
) -> Optional[models.TestSet]:
    """
    Resolve a test set from any valid identifier (UUID, nano_id, or slug).
    Returns None if not found or if there's an error parsing the identifier.

    Raises:
        ItemDeletedException: If the identifier resolves to a soft-deleted
            test set. Not caught here so callers get the same 410 behavior as
            a direct ID lookup.
    """
    try:
        # First try UUID
        try:
            identifier_uuid = uuid.UUID(identifier)
            db_test_set = get_test_set(
                db, test_set_id=identifier_uuid, organization_id=organization_id
            )
        except ValueError:
            # If not UUID, try nano_id or slug
            db_test_set = get_test_set_by_nano_id_or_slug(
                db, identifier, organization_id=organization_id
            )

        return db_test_set
    except ValueError:
        return None


def get_test_sets_for_test(
    db: Session,
    test_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    organization_id: str = None,
    user_id: str = None,
    filter: str | None = None,
) -> tuple[List[models.TestSet], int]:
    """
    Get test sets that contain a given test with pagination, sorting and filtering.

    Args:
        db: Database session
        test_id: ID of the test to find test sets for
        skip: Number of items to skip
        limit: Maximum number of items to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        organization_id: Organization ID for tenant scoping
        user_id: User ID for tenant scoping
        filter: OData filter string

    Returns:
        Tuple containing:
        - List of test sets with their related objects loaded
        - Total count before pagination
    """
    query_builder = (
        QueryBuilder(db, models.TestSet)
        .with_related(*_TEST_SET_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_custom_filter(
            lambda q: q.join(models.test.test_test_set_association).filter(
                and_(
                    models.test.test_test_set_association.c.test_id == test_id,
                    models.test.test_test_set_association.c.organization_id == organization_id,
                )
            )
        )
        .with_odata_filter(filter)
    )

    total_count = query_builder.count()
    items = query_builder.with_pagination(skip, limit).with_sorting(sort_by, sort_order).all()

    return items, total_count


def get_test_set_tests(
    db: Session,
    test_set_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> tuple[List[models.Test], int]:
    """
    Get tests associated with a test set with pagination, sorting and filtering support.

    Args:
        db: Database session
        test_set_id: ID of the test set to get tests for
        skip: Number of items to skip
        limit: Maximum number of items to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string

    Returns:
        Tuple containing:
        - List of tests with their related objects loaded
        - Total count of tests before pagination
    """
    query_builder = (
        QueryBuilder(db, models.Test)
        # Eager-load the relationships TestDetailSchema serializes. with_related
        # picks the strategy per name from its own cardinality, so this can never
        # regress into the 22-join cartesian product that previously materialized
        # multi-GB intermediate result sets on this endpoint -- accidentally adding
        # a one-to-many name here (e.g. test_results/trace) would
        # route through selectin, not joinedload.
        .with_related(
            include(models.Test.prompt),
            include(models.Test.test_type),
            include(models.Test.user),
            include(models.Test.assignee),
            include(models.Test.owner),
            include(models.Test.topic),
            include(models.Test.requirement),
            include(models.Test.category),
            include(models.Test.status),
        )
        .with_visibility_filter()
        .with_custom_filter(
            lambda q: q.join(models.test.test_test_set_association).filter(
                models.test.test_test_set_association.c.test_set_id == test_set_id
            )
        )
        .with_odata_filter(filter)
    )

    # Get total count before pagination
    total_count = query_builder.count()

    # Get paginated results
    items = query_builder.with_pagination(skip, limit).with_sorting(sort_by, sort_order).all()

    return items, total_count


def bulk_delete_test_sets(
    db: Session,
    test_set_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """
    Soft delete multiple test sets in one transaction.

    TestSet's ``visibility`` column is the only ownership gate on delete --
    unlike TestRun, there's no owner-only ":own" rule layered on top -- so
    this is a direct wrapper around the generic bulk helper.
    """
    return bulk_delete_by_ids(
        db,
        models.TestSet,
        test_set_ids,
        organization_id=organization_id,
        user_id=user_id,
    )

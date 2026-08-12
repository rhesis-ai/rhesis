"""
This code implements the CRUD operations for the models in the application.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.database import reset_session_context
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.utils.crud_utils import (
    bulk_delete_by_ids,
    create_item,
    delete_item,
    get_item,
    get_item_detail,
    get_items,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

logger = logging.getLogger(__name__)


# Helper function to print session variables
def get_session_variables(db: Session):
    """Get and return the current PostgreSQL session variables for debugging"""
    results = {}
    try:
        # Check if variables exist before trying to show them
        check_org = db.execute(
            text("SELECT current_setting('app.current_organization', true)")
        ).scalar()
        check_user = db.execute(text("SELECT current_setting('app.current_user', true)")).scalar()

        results["app.current_organization"] = check_org if check_org else "Not set"
        results["app.current_user"] = check_user if check_user else "Not set"

        return results
    except Exception as e:
        logger.debug(f"Error getting session variables: {e}")
        return {"error": str(e)}


# Endpoint CRUD
_ENDPOINT_RELATED_FIELDS = (
    include(models.Endpoint.status),
    include(models.Endpoint.user),
    include(models.Endpoint.project),
)


def get_endpoint(
    db: Session,
    endpoint_id: uuid.UUID,
    organization_id: str,
    user_id: str,
    project_id: str = None,
) -> Optional[models.Endpoint]:
    """Get endpoint with relationships eagerly loaded."""
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.Endpoint)
        .with_deleted()
        .with_related(*_ENDPOINT_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_project_filter(project_id)
        .with_visibility_filter(user_id)
        .filter_by_id(endpoint_id)
    )
    return _check_and_raise_if_deleted(item, models.Endpoint, endpoint_id, False)


def get_endpoints(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Endpoint]:
    return (
        QueryBuilder(db, models.Endpoint)
        .with_related(*_ENDPOINT_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_endpoint(
    db: Session, endpoint: schemas.EndpointCreate, organization_id: str, user_id: str
) -> models.Endpoint:
    """Create endpoint."""
    return create_item(db, models.Endpoint, endpoint, organization_id, user_id)


def update_endpoint(
    db: Session,
    endpoint_id: uuid.UUID,
    endpoint: schemas.EndpointUpdate,
    organization_id: str,
    user_id: str,
) -> Optional[models.Endpoint]:
    """Update endpoint."""
    return update_item(db, models.Endpoint, endpoint_id, endpoint, organization_id, user_id)


def delete_endpoint(
    db: Session, endpoint_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Endpoint]:
    return delete_item(
        db, models.Endpoint, endpoint_id, organization_id=organization_id, user_id=user_id
    )


# Experiment CRUD
def get_experiments(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Experiment]:
    return (
        QueryBuilder(db, models.Experiment)
        .with_related(include(models.Experiment.project))
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


# Prompt CRUD
def get_prompt(
    db: Session, prompt_id: uuid.UUID, organization_id: str = None, user_id: str = None
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
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Prompt]:
    return get_items_detail(
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
    db: Session, prompt: schemas.PromptCreate, organization_id: str = None, user_id: str = None
) -> models.Prompt:
    """Create prompt."""
    return create_item(db, models.Prompt, prompt, organization_id, user_id)


def update_prompt(
    db: Session,
    prompt_id: uuid.UUID,
    prompt: schemas.PromptUpdate,
    organization_id: str = None,
    user_id: str = None,
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
    organization_id: str = None,
    user_id: str = None,
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
    organization_id: str = None,
    user_id: str = None,
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


# Category CRUD
def get_category(
    db: Session, category_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Category]:
    """Get a single category by ID."""
    return get_item(db, models.Category, category_id, organization_id, user_id)


def get_categories(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Category]:
    return get_items(
        db,
        models.Category,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_category(
    db: Session, category: schemas.CategoryCreate, organization_id: str = None, user_id: str = None
) -> models.Category:
    """Create category."""
    return create_item(db, models.Category, category, organization_id, user_id)


def update_category(
    db: Session,
    category_id: uuid.UUID,
    category: schemas.CategoryUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Category]:
    """Update category."""
    return update_item(db, models.Category, category_id, category, organization_id, user_id)


def delete_category(
    db: Session, category_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Category]:
    return delete_item(
        db, models.Category, category_id, organization_id=organization_id, user_id=user_id
    )


# Behavior CRUD
# read_behavior/read_behaviors return BehaviorWithMetricsSchema (tags, user, metrics with
# metric_type/backend_type/tags); status/organization/project are unused, excluded. metrics.tags
# is included explicitly since selectinload's default cascade skips many-to-many relations
# (would otherwise lazy-load tags per nested metric).
_BEHAVIOR_RELATED_FIELDS = (
    include(models.Behavior.user),
    include(models.Behavior._tags_relationship, models.TaggedItem.tag),
    include(models.Behavior.metrics),
    include(models.Behavior.metrics, models.Metric.metric_type),
    include(models.Behavior.metrics, models.Metric.backend_type),
    include(models.Behavior.metrics, models.Metric._tags_relationship, models.TaggedItem.tag),
)


def get_behavior(
    db: Session, behavior_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Behavior]:
    """Get behavior with relationships eagerly loaded."""
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted
    from rhesis.backend.app.utils.query_utils import QueryBuilder

    item = (
        QueryBuilder(db, models.Behavior)
        .with_deleted()
        .with_related(*_BEHAVIOR_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .filter_by_id(behavior_id)
    )
    return _check_and_raise_if_deleted(item, models.Behavior, behavior_id, False)


def get_behaviors(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Behavior]:
    """Get behaviors."""
    return get_items(
        db, models.Behavior, skip, limit, sort_by, sort_order, filter, organization_id, user_id
    )


def get_behaviors_detail(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Behavior]:
    """Get behaviors with related objects for BehaviorWithMetricsSchema, including metrics.

    Runs as two queries, mirroring get_metrics/crud_utils.get_items_detail: a joinless
    query picks the page's IDs (filter + sort + LIMIT/OFFSET), then a second query
    eager-loads _BEHAVIOR_RELATED_FIELDS scoped to just those IDs. Without this split,
    Postgres would have to build every join for every matching row across the org before
    it can sort and cut down to `limit`.
    """
    ordered_ids = (
        QueryBuilder(db, models.Behavior)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .ids()
    )
    if not ordered_ids:
        return []

    items = (
        QueryBuilder(db, models.Behavior)
        .with_related(*_BEHAVIOR_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .query.filter(models.Behavior.id.in_(ordered_ids))
        .all()
    )

    # WHERE id IN (...) does not preserve order -- re-apply the phase-1 sort.
    items_by_id = {item.id: item for item in items}
    return [items_by_id[item_id] for item_id in ordered_ids if item_id in items_by_id]


def create_behavior(
    db: Session, behavior: schemas.BehaviorCreate, organization_id: str = None, user_id: str = None
) -> models.Behavior:
    """Create behavior."""
    return create_item(db, models.Behavior, behavior, organization_id, user_id)


def update_behavior(
    db: Session,
    behavior_id: uuid.UUID,
    behavior: schemas.BehaviorUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Behavior]:
    """Update behavior."""
    return update_item(db, models.Behavior, behavior_id, behavior, organization_id, user_id)


def delete_behavior(
    db: Session, behavior_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Behavior]:
    """Delete behavior."""
    return delete_item(db, models.Behavior, behavior_id, organization_id, user_id)


# TestSet CRUD
def get_test_set(
    db: Session, test_set_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TestSet]:
    """
    Get a test set by its UUID, applying proper visibility filtering and organization scoping.
    """
    return (
        QueryBuilder(db, models.TestSet)
        .with_organization_filter(organization_id)  # Add organization filtering
        .with_visibility_filter(user_id)
        .with_custom_filter(lambda q: q.filter(models.TestSet.id == test_set_id))
        .first()
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
                    subquery_builder.query.join(models.TestConfiguration)
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
    return query_builder.with_explorer_rows_excluded().all()


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
    """
    return (
        QueryBuilder(db, models.TestSet)
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


def resolve_test_set(
    identifier: str, db: Session, organization_id: str = None
) -> Optional[models.TestSet]:
    """
    Resolve a test set from any valid identifier (UUID, nano_id, or slug).
    Returns None if not found or if there's an error parsing the identifier.
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
            include(models.Test.behavior),
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


# TestConfiguration CRUD
def get_test_configuration(
    db: Session, test_configuration_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TestConfiguration]:
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.TestConfiguration)
        .with_deleted()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .filter_by_id(test_configuration_id)
    )
    return _check_and_raise_if_deleted(item, models.TestConfiguration, test_configuration_id, False)


def get_test_configurations(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.TestConfiguration]:
    return (
        QueryBuilder(db, models.TestConfiguration)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_test_configuration(
    db: Session,
    test_configuration: schemas.TestConfigurationCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.TestConfiguration:
    return create_item(
        db,
        models.TestConfiguration,
        test_configuration,
        organization_id=organization_id,
        user_id=user_id,
    )


def update_test_configuration(
    db: Session,
    test_configuration_id: uuid.UUID,
    test_configuration: schemas.TestConfigurationUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TestConfiguration]:
    """Update test_configuration."""
    return update_item(
        db,
        models.TestConfiguration,
        test_configuration_id,
        test_configuration,
        organization_id,
        user_id,
    )


# Status CRUD
def get_status(
    db: Session, status_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Status]:
    """Get a single status by ID."""
    return get_item(db, models.Status, status_id, organization_id, user_id)


def get_statuses(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Status]:
    return get_items(
        db,
        models.Status,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_status(
    db: Session, status: schemas.StatusCreate, organization_id: str = None, user_id: str = None
) -> models.Status:
    """Create status."""
    return create_item(db, models.Status, status, organization_id, user_id)


def update_status(
    db: Session,
    status_id: uuid.UUID,
    status: schemas.StatusUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Status]:
    """Update status."""
    return update_item(db, models.Status, status_id, status, organization_id, user_id)


def delete_status(
    db: Session, status_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Status]:
    """Delete status."""
    return delete_item(db, models.Status, status_id, organization_id, user_id)


# Source CRUD
_SOURCE_RELATED_FIELDS = (
    include(models.Source.source_type),
    include(models.Source.user),
)


def get_source(
    db: Session,
    source_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Source]:
    """Get source.

    Note: Content field is deferred and will not be loaded unless explicitly requested.
    Use get_source_with_content() to load the content field.
    Relationships (source_type, user) are loaded for display.
    """
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.Source)
        .with_deleted()
        .with_related(*_SOURCE_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .filter_by_id(source_id)
    )
    return _check_and_raise_if_deleted(item, models.Source, source_id, False)


def get_source_with_content(
    db: Session,
    source_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
    include_deleted: bool = False,
) -> Optional[models.Source]:
    """Get source with content field explicitly loaded (a deferred column)."""
    from sqlalchemy.orm import undefer

    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.Source)
        .with_deleted()
        .with_related(*_SOURCE_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
    )
    item.query = item.query.options(undefer(models.Source.content))
    item = item.filter_by_id(source_id)
    return _check_and_raise_if_deleted(item, models.Source, source_id, include_deleted)


def get_sources(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Source]:
    """Get sources.

    Note: Content field is deferred and will not be loaded.
    Use get_source_with_content() for individual sources that need content.
    Relationships (source_type, user) are loaded for display.
    """
    return (
        QueryBuilder(db, models.Source)
        .with_related(*_SOURCE_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_source(
    db: Session, source: schemas.SourceCreate, organization_id: str = None, user_id: str = None
) -> models.Source:
    """Create source."""
    return create_item(db, models.Source, source, organization_id, user_id)


def update_source(
    db: Session,
    source_id: uuid.UUID,
    source: schemas.SourceUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Source]:
    """Update source."""
    return update_item(db, models.Source, source_id, source, organization_id, user_id)


def delete_source(
    db: Session, source_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Source]:
    """Delete source."""
    return delete_item(db, models.Source, source_id, organization_id, user_id)


def create_chunk(
    db: Session, chunk: schemas.ChunkCreate, organization_id: str = None, user_id: str = None
) -> models.Chunk:
    """Create chunk."""
    return create_item(db, models.Chunk, chunk, organization_id=organization_id, user_id=user_id)


def update_chunk(
    db: Session,
    chunk_id: uuid.UUID,
    chunk: schemas.ChunkUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Chunk]:
    """Update chunk."""
    return update_item(
        db, models.Chunk, chunk_id, chunk, organization_id=organization_id, user_id=user_id
    )


def delete_chunk(
    db: Session, chunk_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Chunk]:
    """Delete chunk."""
    return delete_item(db, models.Chunk, chunk_id, organization_id=organization_id, user_id=user_id)


def get_chunk(
    db: Session, chunk_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Chunk]:
    """Get chunk."""
    return get_item_detail(
        db, models.Chunk, chunk_id, organization_id=organization_id, user_id=user_id
    )


# Topic CRUD
def get_topic(
    db: Session, topic_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Topic]:
    """Get a single topic by ID."""
    return get_item(db, models.Topic, topic_id, organization_id, user_id)


def get_topics(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Topic]:
    return get_items(
        db,
        models.Topic,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_topic(
    db: Session, topic: schemas.TopicCreate, organization_id: str = None, user_id: str = None
) -> models.Topic:
    """Create topic."""
    return create_item(db, models.Topic, topic, organization_id, user_id)


def update_topic(
    db: Session,
    topic_id: uuid.UUID,
    topic: schemas.TopicUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Topic]:
    """Update topic."""
    return update_item(db, models.Topic, topic_id, topic, organization_id, user_id)


def delete_topic(
    db: Session, topic_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Topic]:
    """Delete topic."""
    return delete_item(db, models.Topic, topic_id, organization_id, user_id)


# User CRUD
def get_user(
    db: Session, user_id: uuid.UUID, organization_id: str = None, tenant_user_id: str = None
) -> Optional[models.User]:
    """Get user."""
    return get_item(db, models.User, user_id, organization_id, tenant_user_id)


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.User]:
    return get_items(
        db,
        models.User,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Create a new user without RLS checks, because we're creating a new user that has no
    organization_id"""
    # Exclude fields not present on the User model
    user_data = user.model_dump(exclude={"send_invite", "project_id"})
    db_user = models.User(**user_data)
    db.add(db_user)
    # Flush to get ID and other generated values before refresh
    db.flush()

    # Seed the default org-role (EE) so the user is not locked out once RBAC is
    # enabled for their org. No-op in community builds / when no org is set.
    if db_user.organization_id is not None:
        from rhesis.backend.app.auth.org_membership_hook import on_user_org_assigned

        on_user_org_assigned(db, db_user.id, db_user.organization_id)

    # Transaction commit is handled by the session context manager
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: uuid.UUID, user: schemas.UserUpdate) -> Optional[models.User]:
    """Update user with special handling for onboarding (no organization)"""
    # Direct query without RLS filters for user updates
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None

    # Update user attributes
    user_data = user.model_dump(exclude_unset=True)
    for key, value in user_data.items():
        setattr(db_user, key, value)

    # Transaction commit/rollback is handled by the session context manager
    return db_user


def delete_user(
    db: Session, target_user_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.User]:
    """
    Remove a user from their organization by setting organization_id to NULL.

    The user account remains active but loses organization access.
    This preserves the user account and all their data while removing
    organizational context. On next login, the user will go through
    the onboarding flow again.

    Also removes all project memberships within the org and clears
    default_project so no orphaned rows or stale settings remain.

    Args:
        db: Database session
        target_user_id: ID of user to remove from organization
        organization_id: Organization ID for tenant context
        user_id: ID of the current user performing the action (for tenant context)

    Returns:
        Updated user object or None if not found

    Raises:
        ValueError: If user tries to delete themselves
    """
    from sqlalchemy.orm.attributes import flag_modified

    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.app.scope import bypass_tenant_filter

    # Security check: Prevent users from deleting themselves
    if str(target_user_id) == str(user_id):
        raise ValueError("Users cannot remove themselves from the organization")

    # Get the user with tenant context
    db_user = get_item(db, models.User, target_user_id, organization_id, user_id)
    if db_user is None:
        return None

    # Drop all project memberships within this org before nulling organization_id,
    # while we can still identify them via the org FK.
    with bypass_tenant_filter():
        memberships = (
            db.query(ProjectMembership)
            .filter_by(user_id=target_user_id, organization_id=organization_id)
            .all()
        )
        for m in memberships:
            db.delete(m)

    # Clear default_project — it's org-scoped so it would be stale after removal.
    if db_user.settings.default_project is not None:
        settings = db_user.settings.raw.copy()
        settings.pop("default_project", None)
        db_user.user_settings = settings
        flag_modified(db_user, "user_settings")

    # Null the org FK last so the membership query above can still use it.
    db_user.organization_id = None

    db.commit()
    db.refresh(db_user)

    return db_user


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    from sqlalchemy import func

    return db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()


def get_user_by_id(db: Session, user_id: Union[str, UUID]) -> Optional[models.User]:
    """Retrieve a user by their ID. Accepts both string and UUID."""
    try:
        # Convert string to UUID if it's a string
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        return db.query(models.User).filter(models.User.id == user_id).first()
    except ValueError:
        # Handle invalid UUID string
        return None


# Organization CRUD
def get_organization(
    db: Session, organization_id: uuid.UUID, tenant_organization_id: str = None, user_id: str = None
) -> Optional[models.Organization]:
    """Get organization."""
    return get_item(db, models.Organization, organization_id, tenant_organization_id, user_id)


def get_organizations(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Organization]:
    return get_items(
        db,
        models.Organization,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_organization(
    db: Session,
    organization: schemas.OrganizationCreate,
    owner_user_id: Optional[UUID] = None,
) -> models.Organization:
    """Create a new organization without RLS checks, because we're creating a new organization.

    When *owner_user_id* is supplied (always the case on the HTTP path) it overrides any
    client-supplied ``owner_id``/``user_id`` values in the schema, making the backend
    authoritative for org ownership (SP3 decision — server-set, cannot be forged).
    Internal callers such as ``local_init.py`` that already supply the correct IDs in the
    schema may pass ``owner_user_id=None`` to preserve the existing behaviour.
    """
    # Print session variables before reset
    before_vars = get_session_variables(db)
    logger.info(f"Session variables BEFORE reset: {before_vars}")

    # Reset session context to ensure the new organization is created correctly
    reset_session_context(db)

    # Verify variables are cleared
    after_vars = get_session_variables(db)
    logger.info(f"Session variables AFTER reset: {after_vars}")

    # Make sure session is clean to avoid RLS issues
    db.expire_all()

    # Convert Pydantic model to dict; project_id is not a column on Organization
    org_data = organization.model_dump(exclude={"project_id"})

    # Backend is authoritative for ownership when owner_user_id is provided.
    if owner_user_id is not None:
        org_data["owner_id"] = str(owner_user_id)
        org_data["user_id"] = str(owner_user_id)

    db_org = models.Organization(**org_data)

    # Add to session - transaction management is handled by context manager
    db.add(db_org)
    db.flush()  # Flush to get the ID

    # Simply return the object without refreshing
    # The refresh operation is what often triggers RLS issues
    logger.info(f"Organization created successfully: {db_org.id}")
    return db_org


def update_organization(
    db: Session, organization_id: uuid.UUID, organization: schemas.OrganizationUpdate
) -> Optional[models.Organization]:
    return update_item(db, models.Organization, organization_id, organization)


def delete_organization(db: Session, organization_id: uuid.UUID) -> Optional[models.Organization]:
    """Delete organization - requires superuser permissions (handled in router)"""
    return delete_item(db, models.Organization, organization_id)


def get_test(
    db: Session, test_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Test]:
    """Get test."""
    return get_item(db, models.Test, test_id, organization_id, user_id)


def get_test_detail(
    db: Session, test_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Test]:
    """Get test with all relationships loaded using optimized approach."""
    return get_item_detail(db, models.Test, test_id, organization_id, user_id)


def get_tests(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Test]:
    """Get tests, minus the Explorer-owned ones (those belong to the /explorer API)."""
    # NOTE: No secondary_sort_by: Test.content sorting is a slow correlated subquery
    return get_items_detail(
        db,
        models.Test,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
        exclude_explorer_rows=True,
    )


def create_test(
    db: Session, test: schemas.TestCreate, organization_id: str = None, user_id: str = None
) -> models.Test:
    """Create test."""
    return create_item(db, models.Test, test, organization_id, user_id)


def update_test(
    db: Session,
    test_id: uuid.UUID,
    test: Dict[str, Any],
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Test]:
    """Update test and refresh parent test set attributes when metadata changes.

    ``test`` must be the resolved update payload (e.g. from
    ``resolve_test_entity_names``), not the raw API schema.
    """
    from rhesis.backend.app.services.test_set import update_test_set_attributes

    metadata_fields = {
        "behavior",
        "behavior_id",
        "topic",
        "topic_id",
        "category",
        "category_id",
        "test_type",
        "test_type_id",
    }
    should_refresh_attributes = bool(metadata_fields & set(test.keys()))

    db_test = update_item(db, models.Test, test_id, test, organization_id, user_id)
    if db_test is None:
        return None

    if should_refresh_attributes:
        affected_test_set_ids = (
            db.execute(
                select(test_test_set_association.c.test_set_id).where(
                    test_test_set_association.c.test_id == test_id,
                    test_test_set_association.c.organization_id == organization_id,
                )
            )
            .scalars()
            .all()
        )

        for test_set_id in affected_test_set_ids:
            update_test_set_attributes(
                db=db,
                test_set_id=str(test_set_id),
                organization_id=organization_id,
                user_id=user_id,
            )

    return db_test


def delete_test(
    db: Session, test_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Test]:
    """
    Soft delete a test and update any associated test sets' attributes.

    The test is marked as deleted but remains in the database to preserve
    referential integrity with test runs, results, and other related data.
    """
    from rhesis.backend.app.services.test_set import update_test_set_attributes

    # Get the test to be deleted
    db_test = get_item(db, models.Test, test_id, organization_id, user_id)
    if db_test is None:
        return None

    # Get all test sets that contain this test before deletion
    test_set_ids = db.execute(
        test_test_set_association.select().where(test_test_set_association.c.test_id == test_id)
    ).fetchall()

    affected_test_set_ids = [row.test_set_id for row in test_set_ids]

    # Soft delete the test (preserves referential integrity)
    db_test.soft_delete()
    db.commit()
    db.refresh(db_test)

    # Update attributes for all affected test sets
    for test_set_id in affected_test_set_ids:
        update_test_set_attributes(
            db=db,
            test_set_id=str(test_set_id),
            organization_id=organization_id,
            user_id=user_id,
        )

    # Return the soft-deleted test
    return db_test


def bulk_delete_tests(
    db: Session,
    test_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """
    Soft delete multiple tests in one transaction and recompute test-set
    attributes once per distinct affected test set (not once per deleted test).

    Deleting the same 25 tests one at a time (25 DELETE /tests/{id} requests)
    recomputes -- and re-UPDATEs -- a shared test set's attributes up to 25
    times, and those concurrent UPDATEs to the same row serialize at the
    database. Resolving the affected test sets across the whole batch up
    front and recomputing each exactly once avoids both problems.
    """
    from rhesis.backend.app.services.test_set import update_test_set_attributes

    if not test_ids:
        return {"deleted_ids": [], "not_found_ids": []}

    def _recompute_affected_test_sets(deleted_ids: List[uuid.UUID]) -> None:
        rows = db.execute(
            test_test_set_association.select().where(
                test_test_set_association.c.test_id.in_(deleted_ids),
                test_test_set_association.c.organization_id == organization_id,
            )
        ).fetchall()
        affected_test_set_ids = {row.test_set_id for row in rows}
        for test_set_id in affected_test_set_ids:
            update_test_set_attributes(
                db=db,
                test_set_id=str(test_set_id),
                organization_id=organization_id,
                user_id=user_id,
            )

    return bulk_delete_by_ids(
        db,
        models.Test,
        test_ids,
        organization_id=organization_id,
        user_id=user_id,
        on_deleted=_recompute_affected_test_sets,
    )


# Test Result CRUD
_TEST_RESULT_RELATED_FIELDS = (
    include(models.TestResult.test_run),
    include(models.TestResult.test),
    include(models.TestResult.test, models.Test.prompt),
    include(models.TestResult.test, models.Test.behavior),
)


def get_test_result(
    db: Session, test_result_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TestResult]:
    """Get test_result with relationships (tags, test, test_run) eagerly loaded."""
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.TestResult)
        .with_deleted()
        .with_related(*_TEST_RESULT_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .filter_by_id(test_result_id)
    )
    return _check_and_raise_if_deleted(item, models.TestResult, test_result_id, False)


def get_test_results(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.TestResult]:
    """Get test_results with relationships (tags, test, test_run) eagerly loaded."""
    return (
        QueryBuilder(db, models.TestResult)
        .with_related(*_TEST_RESULT_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_test_result(
    db: Session,
    test_result: schemas.TestResultCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.TestResult:
    """Create test_result."""
    return create_item(db, models.TestResult, test_result, organization_id, user_id)


def update_test_result(
    db: Session,
    test_result_id: uuid.UUID,
    test_result: schemas.TestResultUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TestResult]:
    """Update test_result."""
    return update_item(db, models.TestResult, test_result_id, test_result, organization_id, user_id)


def delete_test_result(
    db: Session, test_result_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.TestResult]:
    return delete_item(
        db, models.TestResult, test_result_id, organization_id=organization_id, user_id=user_id
    )


# TypeLookup CRUD
def get_type_lookup(
    db: Session, type_lookup_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TypeLookup]:
    """Get type_lookup."""
    return get_item(db, models.TypeLookup, type_lookup_id, organization_id, user_id)


def get_type_lookups(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.TypeLookup]:
    return get_items(
        db,
        models.TypeLookup,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_type_lookup(
    db: Session,
    type_lookup: schemas.TypeLookupCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.TypeLookup:
    """Create type_lookup."""
    return create_item(db, models.TypeLookup, type_lookup, organization_id, user_id)


def update_type_lookup(
    db: Session,
    type_lookup_id: uuid.UUID,
    type_lookup: schemas.TypeLookupUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TypeLookup]:
    """Update type_lookup."""
    return update_item(db, models.TypeLookup, type_lookup_id, type_lookup, organization_id, user_id)


def delete_type_lookup(
    db: Session, type_lookup_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.TypeLookup]:
    """Delete type lookup."""
    return delete_item(db, models.TypeLookup, type_lookup_id, organization_id, user_id)


def get_type_lookup_by_name_and_value(
    db: Session, type_name: str, type_value: str, organization_id: str, user_id: str = None
) -> Optional[models.TypeLookup]:
    """Get a type lookup by its type_name and type_value"""
    return (
        QueryBuilder(db, models.TypeLookup)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(
                models.TypeLookup.type_name == type_name, models.TypeLookup.type_value == type_value
            )
        )
        .first()
    )


# Model CRUD
def get_model(
    db: Session, model_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Model]:
    """Get a specific model by ID with its related objects and organization filtering"""
    query = (
        db.query(models.Model)
        .options(include(models.Model.provider_type))
        .filter(models.Model.id == model_id)
    )

    # Apply organization filtering (SECURITY CRITICAL)
    if organization_id:
        from uuid import UUID as UUIDType

        query = query.filter(models.Model.organization_id == UUIDType(organization_id))

    return query.first()


def get_models(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Model]:
    """Get all models with their related objects"""
    return get_items_detail(
        db,
        models.Model,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_model(
    db: Session, model: schemas.ModelCreate, organization_id: str = None, user_id: str = None
) -> models.Model:
    """Create a new model."""
    return create_item(db, models.Model, model, organization_id, user_id)


def update_model(
    db: Session,
    model_id: uuid.UUID,
    model: schemas.ModelUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Model]:
    """Update a model."""
    # First check if the model is protected
    existing_model = get_model(db, model_id, organization_id)
    if existing_model and getattr(existing_model, "is_protected", False):
        # For protected models, only allow updating certain fields
        # (tags, comments, status, owner, assignee)
        # Block updates to core model configuration properties
        protected_fields = {
            "name",
            "model_name",
            "provider_type_id",
            "key",
            "endpoint",
            "is_protected",
            "icon",
        }

        # Convert model to dict and check if any protected fields are being updated
        update_data = (
            model.model_dump(exclude_unset=True)
            if hasattr(model, "model_dump")
            else model.dict(exclude_unset=True)
        )

        # Check if user is trying to change any protected fields to a different value
        attempted_protected_updates = []
        for field in protected_fields:
            if field in update_data:
                existing_value = getattr(existing_model, field)
                new_value = update_data[field]
                # Only flag as error if the value is actually changing
                if existing_value != new_value:
                    attempted_protected_updates.append(field)

        if attempted_protected_updates:
            fields_str = ", ".join(attempted_protected_updates)
            raise ValueError(
                f"Cannot update protected fields ({fields_str}) on system model. "
                "Only tags, status, owner, and assignee can be modified."
            )

    return update_item(db, models.Model, model_id, model, organization_id, user_id)


def delete_model(
    db: Session, model_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Model]:
    """Delete a model (protected models cannot be deleted)"""
    # First check if the model is protected
    model = get_model(db, model_id, organization_id)
    if model and getattr(model, "is_protected", False):
        raise ValueError("Cannot delete protected system model")

    return delete_item(db, models.Model, model_id, organization_id=organization_id, user_id=user_id)


def test_model_connection(db: Session, model_id: uuid.UUID) -> bool:
    """Test the connection to a model's endpoint

    Args:
        db: Database session
        model_id: ID of the model to test

    Returns:
        bool: True if connection test was successful

    Raises:
        ValueError: If model not found
        Exception: If connection test fails
    """
    # Get the model
    model = get_model(db, model_id)
    if not model:
        raise ValueError(f"Model with id {model_id} not found")

    try:
        # Here you would implement the actual connection test logic
        # This could include making a test request to the model's endpoint
        # For now, we'll just return True
        return True
    except Exception as e:
        raise Exception(f"Failed to test connection: {str(e)}")


# Tool CRUD
_TOOL_RELATED_FIELDS = (include(models.Tool.tool_provider_type),)


def get_tool(
    db: Session, tool_id: uuid.UUID, organization_id: str, user_id: str = None
) -> Optional[models.Tool]:
    """Get a specific tool by ID with relationships loaded"""
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.Tool)
        .with_deleted()
        .with_related(*_TOOL_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .filter_by_id(tool_id)
    )
    return _check_and_raise_if_deleted(item, models.Tool, tool_id, False)


def get_tools(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Tool]:
    """Get all tools for an organization with filtering and pagination"""
    return (
        QueryBuilder(db, models.Tool)
        .with_related(*_TOOL_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def get_tool_by_provider(
    db: Session, organization_id: str, provider_value: str
) -> Optional[models.Tool]:
    """Get organization's tool by provider type_value (e.g., 'notion', 'github')."""
    return (
        db.query(models.Tool)
        .join(models.TypeLookup, models.Tool.tool_provider_type_id == models.TypeLookup.id)
        .filter(
            models.Tool.organization_id == uuid.UUID(organization_id),
            models.TypeLookup.type_value == provider_value,
            models.Tool.deleted_at.is_(None),  # Exclude soft-deleted tools
        )
        .first()
    )


def create_tool(
    db: Session, tool: schemas.ToolCreate, organization_id: str, user_id: str = None
) -> models.Tool:
    """Create a new tool"""
    return create_item(db, models.Tool, tool, organization_id, user_id)


def update_tool(
    db: Session,
    tool_id: uuid.UUID,
    tool: schemas.ToolUpdate,
    organization_id: str,
    user_id: str = None,
) -> Optional[models.Tool]:
    """Update a tool"""
    return update_item(db, models.Tool, tool_id, tool, organization_id, user_id)


def delete_tool(
    db: Session, tool_id: uuid.UUID, organization_id: str, user_id: str = None
) -> Optional[models.Tool]:
    """Delete a tool (soft delete)"""
    return delete_item(db, models.Tool, tool_id, organization_id=organization_id, user_id=user_id)


# ============================================================================
# File CRUD operations
# ============================================================================


def create_file(
    db: Session,
    file_data: Union[schemas.FileCreate, dict],
    organization_id: str = None,
    user_id: str = None,
) -> models.File:
    """Create a file record."""
    if isinstance(file_data, dict):
        file_data = schemas.FileCreate(**file_data)

    if hasattr(file_data, "entity_type") and hasattr(file_data.entity_type, "value"):
        file_data.entity_type = file_data.entity_type.value

    return create_item(db, models.File, file_data, organization_id, user_id)


def get_file(
    db: Session,
    file_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.File]:
    """Get file metadata (content is deferred, not loaded)."""
    return get_item(db, models.File, file_id, organization_id, user_id)


def link_file_to_entity(
    db: Session,
    file_id: uuid.UUID,
    entity_id: uuid.UUID,
    entity_type: str,
) -> Optional[models.File]:
    """Update a File row to link it to a new entity (e.g. a Trace after span storage).

    Pure metadata update — no bytes, no storage writes.
    Returns the updated File, or None if not found.
    """
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if not db_file:
        return None
    db_file.entity_id = entity_id
    db_file.entity_type = entity_type
    db.commit()
    db.refresh(db_file)
    return db_file


def get_files_for_entity(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    organization_id: str = None,
    user_id: str = None,
    skip: int = 0,
    limit: int = 100,
) -> List[models.File]:
    """Get all files for a specific entity (content deferred)."""
    return (
        QueryBuilder(db, models.File)
        .with_organization_filter(organization_id)
        .with_custom_filter(
            lambda q: q.filter(
                models.File.entity_id == entity_id,
                models.File.entity_type == entity_type,
            )
        )
        .with_pagination(skip, limit)
        .with_sorting("position", "asc")
        .all()
    )


def get_entity_files_total_size(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    organization_id: str = None,
) -> int:
    """Get total size in bytes of all files for an entity."""
    query = db.query(func.coalesce(func.sum(models.File.size_bytes), 0)).filter(
        models.File.entity_id == entity_id,
        models.File.entity_type == entity_type,
        models.File.deleted_at.is_(None),
    )
    if organization_id:
        query = query.filter(models.File.organization_id == organization_id)
    return query.scalar()


def get_entity_files_max_position(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    organization_id: str = None,
) -> int:
    """Get the maximum position of files for an entity, or -1 if none exist."""
    query = db.query(func.coalesce(func.max(models.File.position), -1)).filter(
        models.File.entity_id == entity_id,
        models.File.entity_type == entity_type,
        models.File.deleted_at.is_(None),
    )
    if organization_id:
        query = query.filter(models.File.organization_id == organization_id)
    return query.scalar()


def delete_file(
    db: Session,
    file_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.File]:
    """Soft-delete a file."""
    return delete_item(db, models.File, file_id, organization_id, user_id)


# ── Architect Session CRUD ──────────────────────────────────────────────


def get_architect_session(
    db: Session,
    session_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.ArchitectSession]:
    return get_item(db, models.ArchitectSession, session_id, organization_id, user_id)


def get_architect_session_detail(
    db: Session,
    session_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.ArchitectSession]:
    """Get an architect session with its messages eagerly loaded."""
    from rhesis.backend.app.utils.crud_utils import _check_and_raise_if_deleted

    item = (
        QueryBuilder(db, models.ArchitectSession)
        .with_deleted()
        .with_related(include(models.ArchitectSession.messages))
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .filter_by_id(session_id)
    )
    return _check_and_raise_if_deleted(item, models.ArchitectSession, session_id, False)


def get_architect_sessions(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.ArchitectSession]:
    return get_items(
        db,
        models.ArchitectSession,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_architect_session(
    db: Session,
    session: schemas.ArchitectSessionCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.ArchitectSession:
    return create_item(db, models.ArchitectSession, session, organization_id, user_id)


def update_architect_session(
    db: Session,
    session_id: uuid.UUID,
    session: schemas.ArchitectSessionUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.ArchitectSession]:
    return update_item(db, models.ArchitectSession, session_id, session, organization_id, user_id)


def delete_architect_session(
    db: Session,
    session_id: uuid.UUID,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.ArchitectSession]:
    return delete_item(db, models.ArchitectSession, session_id, organization_id, user_id)


# ── Architect Message CRUD ──────────────────────────────────────────────


def get_architect_messages(
    db: Session,
    session_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.ArchitectMessage]:
    query = (
        db.query(models.ArchitectMessage)
        .filter(models.ArchitectMessage.session_id == session_id)
        .filter(models.ArchitectMessage.deleted_at.is_(None))
        .order_by(models.ArchitectMessage.created_at)
        .offset(skip)
        .limit(limit)
    )
    return query.all()


def create_architect_message(
    db: Session,
    message: schemas.ArchitectMessageCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.ArchitectMessage:
    return create_item(db, models.ArchitectMessage, message, organization_id, user_id)

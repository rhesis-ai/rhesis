"""
This code implements the CRUD operations for the models in the application.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.database import reset_session_context
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.schemas.tag import EntityType
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item,
    get_item_detail,
    get_items,
    get_items_detail,
    maintain_tenant_context,
    update_item,
)
from rhesis.backend.app.utils.model_utils import QueryBuilder
from rhesis.backend.app.utils.name_generator import generate_memorable_name
from rhesis.backend.logging import logger


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
def get_endpoint(
    db: Session, endpoint_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Endpoint]:
    """Get endpoint with optimized approach - no session variables needed."""
    return get_item(db, models.Endpoint, endpoint_id, organization_id, user_id)


def get_endpoints(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Endpoint]:
    return get_items_detail(db, models.Endpoint, skip, limit, sort_by, sort_order, filter)


def create_endpoint(
    db: Session, endpoint: schemas.EndpointCreate, organization_id: str = None, user_id: str = None
) -> models.Endpoint:
    """Create endpoint with optimized approach - no session variables needed."""
    return create_item(db, models.Endpoint, endpoint, organization_id, user_id)


def update_endpoint(
    db: Session,
    endpoint_id: uuid.UUID,
    endpoint: schemas.EndpointUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Endpoint]:
    """Update endpoint with optimized approach - no session variables needed."""
    return update_item(db, models.Endpoint, endpoint_id, endpoint, organization_id, user_id)


def delete_endpoint(db: Session, endpoint_id: uuid.UUID) -> Optional[models.Endpoint]:
    return delete_item(db, models.Endpoint, endpoint_id)


# UseCase CRUD
def get_use_case(
    db: Session, use_case_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.UseCase]:
    """Get use_case with optimized approach - no session variables needed."""
    return get_item(db, models.UseCase, use_case_id, organization_id, user_id)


def get_use_cases(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.UseCase]:
    return get_items(db, models.UseCase, skip, limit, sort_by, sort_order, filter)


def create_use_case(
    db: Session, use_case: schemas.UseCaseCreate, organization_id: str = None, user_id: str = None
) -> models.UseCase:
    """Create use_case with optimized approach - no session variables needed."""
    return create_item(db, models.UseCase, use_case, organization_id, user_id)


def update_use_case(
    db: Session,
    use_case_id: uuid.UUID,
    use_case: schemas.UseCaseUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.UseCase]:
    """Update use_case with optimized approach - no session variables needed."""
    return update_item(db, models.UseCase, use_case_id, use_case, organization_id, user_id)


def delete_use_case(db: Session, use_case_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.UseCase]:
    """Delete use case with optimized approach - no session variables needed."""
    return delete_item(db, models.UseCase, use_case_id, organization_id, user_id)


# Prompt CRUD
def get_prompt(
    db: Session, prompt_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Prompt]:
    """Get prompt with optimized approach - no session variables needed."""
    return get_item(db, models.Prompt, prompt_id, organization_id, user_id)


def get_prompts(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Prompt]:
    return get_items(db, models.Prompt, skip, limit, sort_by, sort_order, filter)


def create_prompt(
    db: Session, prompt: schemas.PromptCreate, organization_id: str = None, user_id: str = None
) -> models.Prompt:
    """Create prompt with optimized approach - no session variables needed."""
    return create_item(db, models.Prompt, prompt, organization_id, user_id)


def update_prompt(
    db: Session,
    prompt_id: uuid.UUID,
    prompt: schemas.PromptUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Prompt]:
    """Update prompt with optimized approach - no session variables needed."""
    return update_item(db, models.Prompt, prompt_id, prompt, organization_id, user_id)


def delete_prompt(db: Session, prompt_id: uuid.UUID) -> Optional[models.Prompt]:
    return delete_item(db, models.Prompt, prompt_id)


# Prompt Template CRUD
def get_prompt_template(
    db: Session, prompt_template_id: uuid.UUID
) -> Optional[models.PromptTemplate]:
    return get_item(db, models.PromptTemplate, prompt_template_id)


def get_prompt_templates(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.PromptTemplate]:
    return get_items(db, models.PromptTemplate, skip, limit, sort_by, sort_order, filter)


def create_prompt_template(
    db: Session, prompt_template: schemas.PromptTemplateCreate, organization_id: str = None, user_id: str = None
) -> models.PromptTemplate:
    """Create prompt template with optimized approach - no session variables needed."""
    return create_item(db, models.PromptTemplate, prompt_template, organization_id, user_id)


def update_prompt_template(
    db: Session, prompt_template_id: uuid.UUID, prompt_template: schemas.PromptTemplateUpdate
) -> Optional[models.PromptTemplate]:
    return update_item(db, models.PromptTemplate, prompt_template_id, prompt_template)


def delete_prompt_template(
    db: Session, prompt_template_id: uuid.UUID
) -> Optional[models.PromptTemplate]:
    return delete_item(db, models.PromptTemplate, prompt_template_id)


# Category CRUD
def get_category(
    db: Session, category_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Category]:
    """Get category with optimized approach - no session variables needed."""
    return get_item(db, models.Category, category_id, organization_id, user_id)


def get_categories(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Category]:
    return get_items(db, models.Category, skip, limit, sort_by, sort_order, filter)


def create_category(
    db: Session, category: schemas.CategoryCreate, organization_id: str = None, user_id: str = None
) -> models.Category:
    """Create category with optimized approach - no session variables needed."""
    return create_item(db, models.Category, category, organization_id, user_id)


def update_category(
    db: Session,
    category_id: uuid.UUID,
    category: schemas.CategoryUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Category]:
    """Update category with optimized approach - no session variables needed."""
    return update_item(db, models.Category, category_id, category, organization_id, user_id)


def delete_category(db: Session, category_id: uuid.UUID) -> Optional[models.Category]:
    return delete_item(db, models.Category, category_id)


# Behavior CRUD
def get_behavior(
    db: Session, behavior_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Behavior]:
    """Get behavior with optimized approach - no session variables needed."""
    return get_item(db, models.Behavior, behavior_id, organization_id, user_id)


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
    """Get behaviors with optimized approach - no session variables needed."""
    return get_items(
        db, models.Behavior, skip, limit, sort_by, sort_order, filter, organization_id, user_id
    )


def create_behavior(
    db: Session, behavior: schemas.BehaviorCreate, organization_id: str = None, user_id: str = None
) -> models.Behavior:
    """Create behavior with optimized approach - no session variables needed."""
    return create_item(db, models.Behavior, behavior, organization_id, user_id)


def update_behavior(
    db: Session,
    behavior_id: uuid.UUID,
    behavior: schemas.BehaviorUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Behavior]:
    """Update behavior with optimized approach - no session variables needed."""
    return update_item(db, models.Behavior, behavior_id, behavior, organization_id, user_id)


def delete_behavior(
    db: Session, behavior_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Behavior]:
    """Delete behavior with optimized approach - no session variables needed."""
    return delete_item(db, models.Behavior, behavior_id, organization_id, user_id)


# ResponsePattern CRUD
def get_response_pattern(
    db: Session, response_pattern_id: uuid.UUID
) -> Optional[models.ResponsePattern]:
    return get_item(db, models.ResponsePattern, response_pattern_id)


def get_response_patterns(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.ResponsePattern]:
    return get_items(db, models.ResponsePattern, skip, limit, sort_by, sort_order, filter)


def create_response_pattern(
    db: Session, response_pattern: schemas.ResponsePatternCreate, organization_id: str = None, user_id: str = None
) -> models.ResponsePattern:
    """Create response pattern with optimized approach - no session variables needed."""
    return create_item(db, models.ResponsePattern, response_pattern, organization_id, user_id)


def update_response_pattern(
    db: Session, response_pattern_id: uuid.UUID, response_pattern: schemas.ResponsePatternUpdate
) -> Optional[models.ResponsePattern]:
    return update_item(db, models.ResponsePattern, response_pattern_id, response_pattern)


def delete_response_pattern(
    db: Session, response_pattern_id: uuid.UUID
) -> Optional[models.ResponsePattern]:
    return delete_item(db, models.ResponsePattern, response_pattern_id)


# TestSet CRUD
def get_test_set(db: Session, test_set_id: uuid.UUID) -> Optional[models.TestSet]:
    """
    Get a test set by its UUID, applying proper visibility filtering.
    """
    return (
        QueryBuilder(db, models.TestSet)
        .with_visibility_filter()
        .with_custom_filter(lambda q: q.filter(models.TestSet.id == test_set_id))
        .first()
    )


def get_test_sets(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    has_runs: bool | None = None,
) -> List[models.TestSet]:
    """
    Get test sets with detail loading and proper filtering.
    Public test sets are visible regardless of organization.
    """
    query_builder = (
        QueryBuilder(db, models.TestSet)
        .with_joinedloads()
        .with_visibility_filter()  # This already handles public visibility correctly
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
    )

    # Add test runs filter if specified
    if has_runs is not None:

        def has_runs_filter(query):
            from rhesis.backend.logging import logger

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
                subquery = (
                    db.query(models.TestSet.id)
                    .join(models.TestConfiguration)
                    .join(models.TestRun)
                    .distinct()
                    .subquery()
                )
                filtered_query = query.filter(~models.TestSet.id.in_(subquery))
                logger.info("Applied filter for test sets WITHOUT runs")
                return filtered_query

        query_builder = query_builder.with_custom_filter(has_runs_filter)

    return query_builder.all()


def create_test_set(
    db: Session, test_set: schemas.TestSetCreate, organization_id: str = None, user_id: str = None
) -> models.TestSet:
    """Create test_set with optimized approach - no session variables needed."""
    return create_item(db, models.TestSet, test_set, organization_id, user_id)


def update_test_set(
    db: Session,
    test_set_id: uuid.UUID,
    test_set: schemas.TestSetUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TestSet]:
    """Update test_set with optimized approach - no session variables needed."""
    return update_item(db, models.TestSet, test_set_id, test_set, organization_id, user_id)


def delete_test_set(db: Session, test_set_id: uuid.UUID) -> Optional[models.TestSet]:
    return delete_item(db, models.TestSet, test_set_id)


def get_test_set_by_nano_id_or_slug(db: Session, identifier: str) -> Optional[models.TestSet]:
    """
    Get a test set by its nano_id or slug, applying proper visibility filtering.
    """
    return (
        QueryBuilder(db, models.TestSet)
        .with_joinedloads()
        .with_visibility_filter()
        .with_custom_filter(
            lambda q: q.filter(
                (models.TestSet.nano_id == identifier) | (models.TestSet.slug == identifier)
            )
        )
        .first()
    )


def resolve_test_set(identifier: str, db: Session) -> Optional[models.TestSet]:
    """
    Resolve a test set from any valid identifier (UUID, nano_id, or slug).
    Returns None if not found or if there's an error parsing the identifier.
    """
    try:
        # First try UUID
        try:
            identifier_uuid = uuid.UUID(identifier)
            db_test_set = get_test_set(db, test_set_id=identifier_uuid)
        except ValueError:
            # If not UUID, try nano_id or slug
            db_test_set = get_test_set_by_nano_id_or_slug(db, identifier)

        return db_test_set
    except ValueError:
        return None


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
        .with_joinedloads()
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
    db: Session, test_configuration_id: uuid.UUID
) -> Optional[models.TestConfiguration]:
    return get_item_detail(db, models.TestConfiguration, test_configuration_id)


def get_test_configurations(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.TestConfiguration]:
    return get_items_detail(db, models.TestConfiguration, skip, limit, sort_by, sort_order, filter)


def create_test_configuration(
    db: Session, test_configuration: schemas.TestConfigurationCreate
) -> models.TestConfiguration:
    return create_item(db, models.TestConfiguration, test_configuration)


def update_test_configuration(
    db: Session,
    test_configuration_id: uuid.UUID,
    test_configuration: schemas.TestConfigurationUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TestConfiguration]:
    """Update test_configuration with optimized approach - no session variables needed."""
    return update_item(
        db,
        models.TestConfiguration,
        test_configuration_id,
        test_configuration,
        organization_id,
        user_id,
    )


# Risk CRUD
def get_risk(
    db: Session, risk_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Risk]:
    """Get risk with optimized approach - no session variables needed."""
    return get_item(db, models.Risk, risk_id, organization_id, user_id)


def get_risks(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Risk]:
    return get_items(db, models.Risk, skip, limit, sort_by, sort_order, filter)


def create_risk(
    db: Session, risk: schemas.RiskCreate, organization_id: str = None, user_id: str = None
) -> models.Risk:
    """Create risk with optimized approach - no session variables needed."""
    return create_item(db, models.Risk, risk, organization_id, user_id)


def update_risk(
    db: Session,
    risk_id: uuid.UUID,
    risk: schemas.RiskUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Risk]:
    """Update risk with optimized approach - no session variables needed."""
    return update_item(db, models.Risk, risk_id, risk, organization_id, user_id)


def delete_risk(db: Session, risk_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.Risk]:
    """Delete risk with optimized approach - no session variables needed."""
    return delete_item(db, models.Risk, risk_id, organization_id, user_id)


# Status CRUD
def get_status(
    db: Session, status_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Status]:
    """Get status with optimized approach - no session variables needed."""
    return get_item(db, models.Status, status_id, organization_id, user_id)


def get_statuses(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Status]:
    return get_items(db, models.Status, skip, limit, sort_by, sort_order, filter)


def create_status(
    db: Session, status: schemas.StatusCreate, organization_id: str = None, user_id: str = None
) -> models.Status:
    """Create status with optimized approach - no session variables needed."""
    return create_item(db, models.Status, status, organization_id, user_id)


def update_status(
    db: Session,
    status_id: uuid.UUID,
    status: schemas.StatusUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Status]:
    """Update status with optimized approach - no session variables needed."""
    return update_item(db, models.Status, status_id, status, organization_id, user_id)


def delete_status(db: Session, status_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.Status]:
    """Delete status with optimized approach - no session variables needed."""
    return delete_item(db, models.Status, status_id, organization_id, user_id)


# Source CRUD
def get_source(
    db: Session, source_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Source]:
    """Get source with optimized approach - no session variables needed."""
    return get_item(db, models.Source, source_id, organization_id, user_id)


def get_sources(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Source]:
    return get_items(db, models.Source, skip, limit, sort_by, sort_order, filter)


def create_source(
    db: Session, source: schemas.SourceCreate, organization_id: str = None, user_id: str = None
) -> models.Source:
    """Create source with optimized approach - no session variables needed."""
    return create_item(db, models.Source, source, organization_id, user_id)


def update_source(
    db: Session,
    source_id: uuid.UUID,
    source: schemas.SourceUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Source]:
    """Update source with optimized approach - no session variables needed."""
    return update_item(db, models.Source, source_id, source, organization_id, user_id)


def delete_source(db: Session, source_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.Source]:
    """Delete source with optimized approach - no session variables needed."""
    return delete_item(db, models.Source, source_id, organization_id, user_id)


# Topic CRUD
def get_topic(
    db: Session, topic_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Topic]:
    """Get topic with optimized approach - no session variables needed."""
    return get_item(db, models.Topic, topic_id, organization_id, user_id)


def get_topics(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Topic]:
    return get_items(db, models.Topic, skip, limit, sort_by, sort_order, filter)


def create_topic(
    db: Session, topic: schemas.TopicCreate, organization_id: str = None, user_id: str = None
) -> models.Topic:
    """Create topic with optimized approach - no session variables needed."""
    return create_item(db, models.Topic, topic, organization_id, user_id)


def update_topic(
    db: Session,
    topic_id: uuid.UUID,
    topic: schemas.TopicUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Topic]:
    """Update topic with optimized approach - no session variables needed."""
    return update_item(db, models.Topic, topic_id, topic, organization_id, user_id)


def delete_topic(db: Session, topic_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.Topic]:
    """Delete topic with optimized approach - no session variables needed."""
    return delete_item(db, models.Topic, topic_id, organization_id, user_id)


# Demographic CRUD
def get_demographic(
    db: Session, demographic_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Demographic]:
    """Get demographic with optimized approach - no session variables needed."""
    return get_item(db, models.Demographic, demographic_id, organization_id, user_id)


def get_demographics(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Demographic]:
    return get_items(db, models.Demographic, skip, limit, sort_by, sort_order, filter)


def create_demographic(
    db: Session,
    demographic: schemas.DemographicCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.Demographic:
    """Create demographic with optimized approach - no session variables needed."""
    return create_item(db, models.Demographic, demographic, organization_id, user_id)


def update_demographic(
    db: Session,
    demographic_id: uuid.UUID,
    demographic: schemas.DemographicUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Demographic]:
    """Update demographic with optimized approach - no session variables needed."""
    return update_item(
        db, models.Demographic, demographic_id, demographic, organization_id, user_id
    )


def delete_demographic(db: Session, demographic_id: uuid.UUID) -> Optional[models.Demographic]:
    return delete_item(db, models.Demographic, demographic_id)


# Dimension CRUD
def get_dimension(
    db: Session, dimension_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Dimension]:
    """Get dimension with optimized approach - no session variables needed."""
    return get_item(db, models.Dimension, dimension_id, organization_id, user_id)


def get_dimensions(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Dimension]:
    return get_items(db, models.Dimension, skip, limit, sort_by, sort_order, filter)


def create_dimension(
    db: Session,
    dimension: schemas.DimensionCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.Dimension:
    """Create dimension with optimized approach - no session variables needed."""
    return create_item(db, models.Dimension, dimension, organization_id, user_id)


def update_dimension(
    db: Session,
    dimension_id: uuid.UUID,
    dimension: schemas.DimensionUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Dimension]:
    """Update dimension with optimized approach - no session variables needed."""
    return update_item(db, models.Dimension, dimension_id, dimension, organization_id, user_id)


def delete_dimension(db: Session, dimension_id: uuid.UUID) -> Optional[models.Dimension]:
    return delete_item(db, models.Dimension, dimension_id)


# User CRUD
def get_user(
    db: Session, user_id: uuid.UUID, organization_id: str = None, tenant_user_id: str = None
) -> Optional[models.User]:
    """Get user with optimized approach - no session variables needed."""
    return get_item(db, models.User, user_id, organization_id, tenant_user_id)


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.User]:
    return get_items(db, models.User, skip, limit, sort_by, sort_order, filter)


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Create a new user without RLS checks, because we're creating a new user that has no
    organization_id"""
    # Exclude send_invite field since it's not part of the User model
    user_data = user.dict(exclude={"send_invite"})
    db_user = models.User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: uuid.UUID, user: schemas.UserUpdate) -> Optional[models.User]:
    """Update user with special handling for onboarding (no organization)"""
    try:
        # Direct query without RLS filters for user updates
        db_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not db_user:
            return None

        # Update user attributes
        user_data = user.model_dump(exclude_unset=True)
        for key, value in user_data.items():
            setattr(db_user, key, value)

        db.commit()
        return db_user
    except Exception as e:
        db.rollback()
        logger.debug(f"Error updating user: {e}")
        raise


def delete_user(db: Session, user_id: uuid.UUID) -> Optional[models.User]:
    return delete_item(db, models.User, user_id)


def get_user_by_auth0_id(db: Session, auth0_id: str) -> Optional[models.User]:
    """Get a user by their Auth0 ID"""
    return db.query(models.User).filter(models.User.auth0_id == auth0_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


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


# Tag CRUD
def get_tag(
    db: Session, tag_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Tag]:
    """Get tag with optimized approach - no session variables needed."""
    return get_item(db, models.Tag, tag_id, organization_id, user_id)


def get_tags(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Tag]:
    return get_items(db, models.Tag, skip, limit, sort_by, sort_order, filter)


def create_tag(
    db: Session, tag: schemas.TagCreate, organization_id: str = None, user_id: str = None
) -> models.Tag:
    """Create tag with optimized approach - no session variables needed."""
    return create_item(db, models.Tag, tag, organization_id, user_id)


def update_tag(
    db: Session,
    tag_id: uuid.UUID,
    tag: schemas.TagUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Tag]:
    """Update tag with optimized approach - no session variables needed."""
    return update_item(db, models.Tag, tag_id, tag, organization_id, user_id)


def delete_tag(db: Session, tag_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.Tag]:
    """Delete tag with optimized approach - no session variables needed."""
    return delete_item(db, models.Tag, tag_id, organization_id, user_id)


def assign_tag(
    db: Session, tag: schemas.TagCreate, entity_id: UUID, entity_type: EntityType
) -> models.Tag:
    """Create a tag if it doesn't exist and link it to an entity"""
    # Get the actual model class based on entity_type
    model_class = getattr(models, entity_type.value)

    # Verify the entity exists
    entity = db.query(model_class).filter(model_class.id == entity_id).first()
    if not entity:
        raise ValueError(f"{entity_type.value} with id {entity_id} not found")

    # Check if tag already exists (keep organization filter for double security)
    db_tag = (
        db.query(models.Tag)
        .filter(models.Tag.name == tag.name, models.Tag.organization_id == tag.organization_id)
        .first()
    )

    # If tag doesn't exist, create it
    if not db_tag:
        db_tag = create_tag(db=db, tag=tag)

    # Check if the tag is already assigned
    existing_assignment = (
        db.query(models.TaggedItem)
        .filter(
            models.TaggedItem.tag_id == db_tag.id,
            models.TaggedItem.entity_id == entity_id,
            models.TaggedItem.entity_type == entity_type.value,
            models.TaggedItem.organization_id
            == tag.organization_id,  # Add organization filter here too
        )
        .first()
    )

    if existing_assignment:
        return db_tag

    # Create the tagged_item relationship
    tagged_item = models.TaggedItem(
        tag_id=db_tag.id,
        entity_id=entity_id,
        entity_type=entity_type.value,
        organization_id=tag.organization_id,
        user_id=tag.user_id,
    )
    db.add(tagged_item)
    with maintain_tenant_context(db):
        db.commit()
        db.refresh(db_tag)

    return db_tag


def remove_tag(db: Session, tag_id: UUID, entity_id: UUID, entity_type: EntityType) -> bool:
    """Remove a tag from an entity by deleting the tagged_item relationship"""
    # Get the tag to check organization
    db_tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not db_tag:
        raise ValueError("Tag not found")

    # Verify the entity exists
    model_class = getattr(models, entity_type.value)
    entity = db.query(model_class).filter(model_class.id == entity_id).first()
    if not entity:
        raise ValueError(f"{entity_type.value} with id {entity_id} not found")

    result = (
        db.query(models.TaggedItem)
        .filter(
            models.TaggedItem.tag_id == tag_id,
            models.TaggedItem.entity_id == entity_id,
            models.TaggedItem.entity_type == entity_type.value,
            models.TaggedItem.organization_id == db_tag.organization_id,  # Add organization filter
        )
        .delete()
    )

    with maintain_tenant_context(db):
        db.commit()
    return result > 0


# Token CRUD
def get_token(
    db: Session, token_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Token]:
    """Get token with optimized approach - no session variables needed."""
    return get_item(db, models.Token, token_id, organization_id, user_id)


def get_tokens(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Token]:
    return get_items(db, models.Token, skip, limit, sort_by, sort_order, filter)


def get_user_tokens(
    db: Session,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    valid_only: bool = False,
) -> List[models.Token]:
    """Get all active bearer tokens for a user with pagination and sorting

    Args:
        db: Database session
        user_id: User ID to get tokens for
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string
        valid_only: If True, only returns valid (non-expired) tokens

    Returns:
        List of token objects
    """
    query_builder = (
        QueryBuilder(db, models.Token)
        .with_organization_filter()
        .with_custom_filter(
            lambda q: q.filter(models.Token.user_id == user_id, models.Token.token_type == "bearer")
        )
    )

    # Add validity check if requested
    if valid_only:
        now = datetime.now(timezone.utc)
        query_builder = query_builder.with_custom_filter(
            lambda q: q.filter(
                # Token is either never-expiring (expires_at is None) or not yet expired
                (models.Token.expires_at.is_(None)) | (models.Token.expires_at > now)
            )
        )

    return (
        query_builder.with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def create_token(
    db: Session, token: schemas.TokenCreate, organization_id: str = None, user_id: str = None
) -> models.Token:
    """Create token with optimized approach - no session variables needed."""
    return create_item(db, models.Token, token, organization_id, user_id)


def update_token(
    db: Session, token_id: uuid.UUID, token: schemas.TokenUpdate, organization_id: str = None, user_id: str = None
) -> Optional[models.Token]:
    """Update token with optimized approach - no session variables needed."""
    return update_item(db, models.Token, token_id, token, organization_id, user_id)


def revoke_token(db: Session, token_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.Token]:
    """Delete token with optimized approach - no session variables needed."""
    return delete_item(db, models.Token, token_id, organization_id, user_id)


def revoke_user_tokens(db: Session, user_id: uuid.UUID) -> List[models.Token]:
    result = db.query(models.Token).filter(models.Token.user_id == user_id).delete()
    with maintain_tenant_context(db):
        db.commit()
    return result


def get_token_by_value(db: Session, token_value: str):
    """Retrieve a token by its value"""
    token = db.query(models.Token).filter(models.Token.token == token_value).first()
    return token


# Organization CRUD
def get_organization(
    db: Session, organization_id: uuid.UUID, tenant_organization_id: str = None, user_id: str = None
) -> Optional[models.Organization]:
    """Get organization with optimized approach - no session variables needed."""
    return get_item(db, models.Organization, organization_id, tenant_organization_id, user_id)


def get_organizations(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Organization]:
    return get_items(db, models.Organization, skip, limit, sort_by, sort_order, filter)


def create_organization(
    db: Session, organization: schemas.OrganizationCreate
) -> models.Organization:
    """Create a new organization without RLS checks, because we're creating a new organization"""
    try:
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

        # Convert Pydantic model to dict
        org_data = (
            organization.dict() if hasattr(organization, "dict") else organization.model_dump()
        )
        db_org = models.Organization(**org_data)

        # Add and commit in a simple transaction
        db.add(db_org)
        db.commit()

        # Simply return the object without refreshing
        # The refresh operation is what often triggers RLS issues
        logger.info(f"Organization created successfully: {db_org.id}")
        return db_org
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating organization: {str(e)}")
        raise ValueError(f"Failed to create organization: {str(e)}")


def update_organization(
    db: Session, organization_id: uuid.UUID, organization: schemas.OrganizationUpdate
) -> Optional[models.Organization]:
    return update_item(db, models.Organization, organization_id, organization)


def delete_organization(db: Session, organization_id: uuid.UUID) -> Optional[models.Organization]:
    """Delete organization - requires superuser permissions (handled in router)"""
    return delete_item(db, models.Organization, organization_id)


# Project CRUD
def get_project(
    db: Session, project_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Project]:
    """Get project with optimized approach - no session variables needed."""
    return get_item(db, models.Project, project_id, organization_id, user_id)


def get_projects(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Project]:
    return get_items_detail(db, models.Project, skip, limit, sort_by, sort_order, filter)


def create_project(
    db: Session, project: schemas.ProjectCreate, organization_id: str = None, user_id: str = None
) -> models.Project:
    """Create project with optimized approach - no session variables needed."""
    return create_item(db, models.Project, project, organization_id, user_id)


def update_project(
    db: Session, project_id: uuid.UUID, project: schemas.ProjectUpdate
) -> Optional[models.Project]:
    return update_item(db, models.Project, project_id, project)


def get_test(
    db: Session, test_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Test]:
    """Get test with optimized approach - no session variables needed."""
    return get_item(db, models.Test, test_id, organization_id, user_id)


def get_tests(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Test]:
    return get_items_detail(db, models.Test, skip, limit, sort_by, sort_order, filter)


def create_test(
    db: Session, test: schemas.TestCreate, organization_id: str = None, user_id: str = None
) -> models.Test:
    """Create test with optimized approach - no session variables needed."""
    return create_item(db, models.Test, test, organization_id, user_id)


def update_test(
    db: Session,
    test_id: uuid.UUID,
    test: schemas.TestUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Test]:
    """Update test with optimized approach - no session variables needed."""
    return update_item(db, models.Test, test_id, test, organization_id, user_id)


def delete_test(db: Session, test_id: uuid.UUID) -> Optional[models.Test]:
    """Delete a test and update any associated test sets' attributes"""
    from rhesis.backend.app.services.test_set import update_test_set_attributes

    with maintain_tenant_context(db):
        # Get the test to be deleted
        db_test = get_item(db, models.Test, test_id)
        if db_test is None:
            return None

        # Get all test sets that contain this test before deletion
        test_set_ids = db.execute(
            test_test_set_association.select().where(test_test_set_association.c.test_id == test_id)
        ).fetchall()

        affected_test_set_ids = [row.test_set_id for row in test_set_ids]

        # Store a copy of the test before deletion
        deleted_test = db_test

        # Delete the test (this will also cascade delete the associations)
        db.delete(db_test)
        db.flush()

        # Update attributes for all affected test sets
        for test_set_id in affected_test_set_ids:
            update_test_set_attributes(db=db, test_set_id=str(test_set_id))

        db.commit()
        return deleted_test


# TestContext CRUD
def get_test_context(
    db: Session, test_context_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TestContext]:
    """Get test_context with optimized approach - no session variables needed."""
    return get_item(db, models.TestContext, test_context_id, organization_id, user_id)


def get_test_contexts(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.TestContext]:
    return get_items(db, models.TestContext, skip, limit, sort_by, sort_order, filter)


def get_test_contexts_by_test(db: Session, test_id: uuid.UUID) -> List[models.TestContext]:
    return (
        QueryBuilder(db, models.TestContext)
        .with_organization_filter()
        .with_custom_filter(lambda q: q.filter(models.TestContext.test_id == test_id))
        .all()
    )


def create_test_context(
    db: Session,
    test_context: schemas.TestContextCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.TestContext:
    """Create test_context with optimized approach - no session variables needed."""
    return create_item(db, models.TestContext, test_context, organization_id, user_id)


def update_test_context(
    db: Session,
    test_context_id: uuid.UUID,
    test_context: schemas.TestContextUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TestContext]:
    """Update test_context with optimized approach - no session variables needed."""
    return update_item(
        db, models.TestContext, test_context_id, test_context, organization_id, user_id
    )


def delete_test_context(db: Session, test_context_id: uuid.UUID) -> Optional[models.TestContext]:
    return delete_item(db, models.TestContext, test_context_id)


# Test Run CRUD
def get_test_run(
    db: Session, test_run_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TestRun]:
    """Get test_run with optimized approach - no session variables needed."""
    return get_item(db, models.TestRun, test_run_id, organization_id, user_id)


def get_test_runs(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.TestRun]:
    return get_items_detail(db, models.TestRun, skip, limit, sort_by, sort_order, filter)


def get_test_run_behaviors(db: Session, test_run_id: uuid.UUID) -> List[models.Behavior]:
    """Get behaviors that have test results for a specific test run"""
    # Verify the test run exists
    test_run = get_test_run(db, test_run_id)
    if not test_run:
        raise ValueError(f"Test run with id {test_run_id} not found")

    # Get unique behavior IDs from tests that have results in this test run
    behavior_ids_query = (
        db.query(models.Test.behavior_id)
        .join(models.TestResult, models.Test.id == models.TestResult.test_id)
        .filter(
            models.TestResult.test_run_id == test_run_id,
            models.Test.behavior_id.isnot(None),  # Only tests that have a behavior
        )
        .distinct()
    )

    behavior_ids = [row[0] for row in behavior_ids_query.all()]

    if not behavior_ids:
        return []

    # Get the actual behavior objects with proper filtering
    return (
        QueryBuilder(db, models.Behavior)
        .with_visibility_filter()
        .with_custom_filter(lambda q: q.filter(models.Behavior.id.in_(behavior_ids)))
        .with_sorting("name", "asc")
        .all()
    )


def create_test_run(db: Session, test_run: schemas.TestRunCreate) -> models.TestRun:
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

    return create_item(db, models.TestRun, test_run)


def update_test_run(
    db: Session,
    test_run_id: uuid.UUID,
    test_run: schemas.TestRunUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TestRun]:
    """Update test_run with optimized approach - no session variables needed."""
    return update_item(db, models.TestRun, test_run_id, test_run, organization_id, user_id)


def delete_test_run(db: Session, test_run_id: uuid.UUID) -> Optional[models.TestRun]:
    return delete_item(db, models.TestRun, test_run_id)


# Test Result CRUD
def get_test_result(
    db: Session, test_result_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TestResult]:
    """Get test_result with optimized approach - no session variables needed."""
    return get_item(db, models.TestResult, test_result_id, organization_id, user_id)


def get_test_results(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.TestResult]:
    return get_items(db, models.TestResult, skip, limit, sort_by, sort_order, filter)


def create_test_result(
    db: Session,
    test_result: schemas.TestResultCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.TestResult:
    """Create test_result with optimized approach - no session variables needed."""
    return create_item(db, models.TestResult, test_result, organization_id, user_id)


def update_test_result(
    db: Session,
    test_result_id: uuid.UUID,
    test_result: schemas.TestResultUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TestResult]:
    """Update test_result with optimized approach - no session variables needed."""
    return update_item(db, models.TestResult, test_result_id, test_result, organization_id, user_id)


def delete_test_result(db: Session, test_result_id: uuid.UUID) -> Optional[models.TestResult]:
    return delete_item(db, models.TestResult, test_result_id)


def delete_project(db: Session, project_id: uuid.UUID) -> Optional[models.Project]:
    return delete_item(db, models.Project, project_id)


# TypeLookup CRUD
def get_type_lookup(
    db: Session, type_lookup_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.TypeLookup]:
    """Get type_lookup with optimized approach - no session variables needed."""
    return get_item(db, models.TypeLookup, type_lookup_id, organization_id, user_id)


def get_type_lookups(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.TypeLookup]:
    return get_items(db, models.TypeLookup, skip, limit, sort_by, sort_order, filter)


def create_type_lookup(
    db: Session,
    type_lookup: schemas.TypeLookupCreate,
    organization_id: str = None,
    user_id: str = None,
) -> models.TypeLookup:
    """Create type_lookup with optimized approach - no session variables needed."""
    return create_item(db, models.TypeLookup, type_lookup, organization_id, user_id)


def update_type_lookup(
    db: Session,
    type_lookup_id: uuid.UUID,
    type_lookup: schemas.TypeLookupUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.TypeLookup]:
    """Update type_lookup with optimized approach - no session variables needed."""
    return update_item(db, models.TypeLookup, type_lookup_id, type_lookup, organization_id, user_id)


def delete_type_lookup(db: Session, type_lookup_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.TypeLookup]:
    """Delete type lookup with optimized approach - no session variables needed."""
    return delete_item(db, models.TypeLookup, type_lookup_id, organization_id, user_id)


def get_type_lookup_by_name_and_value(
    db: Session, type_name: str, type_value: str
) -> Optional[models.TypeLookup]:
    """Get a type lookup by its type_name and type_value"""
    return (
        QueryBuilder(db, models.TypeLookup)
        .with_organization_filter()
        .with_custom_filter(
            lambda q: q.filter(
                models.TypeLookup.type_name == type_name, models.TypeLookup.type_value == type_value
            )
        )
        .first()
    )


# Metric CRUD
def get_metric(db: Session, metric_id: uuid.UUID) -> Optional[models.Metric]:
    """Get a specific metric by ID with its related objects, including many-to-many relationships"""
    with maintain_tenant_context(db):
        return (
            QueryBuilder(db, models.Metric)
            .with_joinedloads(skip_many_to_many=False)  # Include many-to-many relationships
            .with_organization_filter()
            .with_visibility_filter()
            .with_custom_filter(lambda q: q.filter(models.Metric.id == metric_id))
            .first()
        )


def get_metrics(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Metric]:
    """Get all metrics with their related objects, including many-to-many relationships"""
    with maintain_tenant_context(db):
        return (
            QueryBuilder(db, models.Metric)
            .with_joinedloads(skip_many_to_many=False)  # Include many-to-many relationships
            .with_organization_filter()
            .with_visibility_filter()
            .with_odata_filter(filter)
            .with_pagination(skip, limit)
            .with_sorting(sort_by, sort_order)
            .all()
        )


def create_metric(
    db: Session, metric: schemas.MetricCreate, organization_id: str = None, user_id: str = None
) -> models.Metric:
    """Create a new metric with optimized approach - no session variables needed."""
    return create_item(db, models.Metric, metric, organization_id, user_id)


def update_metric(
    db: Session,
    metric_id: uuid.UUID,
    metric: schemas.MetricUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Metric]:
    """Update a metric with optimized approach - no session variables needed."""
    return update_item(db, models.Metric, metric_id, metric, organization_id, user_id)


def delete_metric(db: Session, metric_id: uuid.UUID) -> Optional[models.Metric]:
    """Delete a metric"""
    return delete_item(db, models.Metric, metric_id)


def add_behavior_to_metric(
    db: Session, metric_id: UUID, behavior_id: UUID, user_id: UUID, organization_id: UUID
) -> bool:
    """Add a behavior to a metric.

    Args:
        db: Database session
        metric_id: ID of the metric
        behavior_id: ID of the behavior to add
        user_id: ID of the user performing the operation
        organization_id: ID of the organization

    Returns:
        bool: True if the behavior was added, False if it was already associated
    """
    # Verify the metric exists
    metric = db.query(models.Metric).filter(models.Metric.id == metric_id).first()
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found")

    # Verify the behavior exists
    behavior = db.query(models.Behavior).filter(models.Behavior.id == behavior_id).first()
    if not behavior:
        raise ValueError(f"Behavior with id {behavior_id} not found")

    # Check if the association already exists
    existing = (
        db.query(models.behavior_metric_association)
        .filter(
            models.behavior_metric_association.c.metric_id == metric_id,
            models.behavior_metric_association.c.behavior_id == behavior_id,
            models.behavior_metric_association.c.organization_id == organization_id,
        )
        .first()
    )

    if existing:
        return False

    # Create the association
    db.execute(
        models.behavior_metric_association.insert().values(
            metric_id=metric_id,
            behavior_id=behavior_id,
            user_id=user_id,
            organization_id=organization_id,
        )
    )

    with maintain_tenant_context(db):
        db.commit()
    return True


def remove_behavior_from_metric(
    db: Session, metric_id: UUID, behavior_id: UUID, organization_id: UUID
) -> bool:
    """Remove a behavior from a metric.

    Args:
        db: Database session
        metric_id: ID of the metric
        behavior_id: ID of the behavior to remove
        organization_id: ID of the organization

    Returns:
        bool: True if the behavior was removed, False if it wasn't associated
    """
    # Verify the metric exists
    metric = db.query(models.Metric).filter(models.Metric.id == metric_id).first()
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found")

    # Verify the behavior exists
    behavior = db.query(models.Behavior).filter(models.Behavior.id == behavior_id).first()
    if not behavior:
        raise ValueError(f"Behavior with id {behavior_id} not found")

    result = (
        db.query(models.behavior_metric_association)
        .filter(
            models.behavior_metric_association.c.metric_id == metric_id,
            models.behavior_metric_association.c.behavior_id == behavior_id,
            models.behavior_metric_association.c.organization_id == organization_id,
        )
        .delete()
    )

    with maintain_tenant_context(db):
        db.commit()
    return result > 0


def get_metric_behaviors(
    db: Session,
    metric_id: UUID,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Behavior]:
    """Get all behaviors associated with a metric.

    Args:
        db: Database session
        metric_id: ID of the metric
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string

    Returns:
        List of behaviors associated with the metric
    """
    # Verify the metric exists
    metric = db.query(models.Metric).filter(models.Metric.id == metric_id).first()
    if not metric:
        raise ValueError(f"Metric with id {metric_id} not found")

    return (
        QueryBuilder(db, models.Behavior)
        .with_organization_filter()
        .with_custom_filter(
            lambda q: q.join(models.behavior_metric_association).filter(
                models.behavior_metric_association.c.metric_id == metric_id
            )
        )
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def get_behavior_metrics(
    db: Session,
    behavior_id: UUID,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Metric]:
    """Get all metrics associated with a behavior.

    Args:
        db: Database session
        behavior_id: ID of the behavior
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string

    Returns:
        List of metrics associated with the behavior
    """
    # Verify the behavior exists
    behavior = db.query(models.Behavior).filter(models.Behavior.id == behavior_id).first()
    if not behavior:
        raise ValueError(f"Behavior with id {behavior_id} not found")

    return (
        QueryBuilder(db, models.Metric)
        .with_organization_filter()
        .with_custom_filter(
            lambda q: q.join(models.behavior_metric_association).filter(
                models.behavior_metric_association.c.behavior_id == behavior_id
            )
        )
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


# Model CRUD
def get_model(db: Session, model_id: uuid.UUID) -> Optional[models.Model]:
    """Get a specific model by ID with its related objects"""
    return get_item_detail(db, models.Model, model_id)


def get_models(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Model]:
    """Get all models with their related objects"""
    return get_items_detail(db, models.Model, skip, limit, sort_by, sort_order, filter)


def create_model(
    db: Session, model: schemas.ModelCreate, organization_id: str = None, user_id: str = None
) -> models.Model:
    """Create a new model with optimized approach - no session variables needed."""
    return create_item(db, models.Model, model, organization_id, user_id)


def update_model(
    db: Session,
    model_id: uuid.UUID,
    model: schemas.ModelUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Model]:
    """Update a model with optimized approach - no session variables needed."""
    return update_item(db, models.Model, model_id, model, organization_id, user_id)


def delete_model(db: Session, model_id: uuid.UUID) -> Optional[models.Model]:
    """Delete a model"""
    return delete_item(db, models.Model, model_id)


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


# Comment CRUD
def get_comment(db: Session, comment_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.Comment]:
    """Get a specific comment by ID with optimized tenant context"""
    return get_item(db, models.Comment, comment_id, organization_id, user_id)


def get_comments(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Comment]:
    """Get all comments with filtering and pagination"""
    return get_items_detail(db, models.Comment, skip, limit, sort_by, sort_order, filter)


def get_comments_by_entity(
    db: Session,
    entity_id: uuid.UUID,
    entity_type: str,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> List[models.Comment]:
    """Get all comments for a specific entity (test, test_set, test_run)"""
    return (
        QueryBuilder(db, models.Comment)
        .with_organization_filter()
        .with_custom_filter(
            lambda q: q.filter(
                models.Comment.entity_id == entity_id, models.Comment.entity_type == entity_type
            )
        )
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def create_comment(
    db: Session,
    comment: Union[schemas.CommentCreate, dict],
    organization_id: str = None,
    user_id: str = None,
) -> models.Comment:
    """Create comment with optimized approach - no session variables needed."""
    # If it's a dict, convert it to CommentCreate schema first
    if isinstance(comment, dict):
        comment = schemas.CommentCreate(**comment)

    # Convert enum to string if it's still an enum object
    if hasattr(comment, "entity_type") and hasattr(comment.entity_type, "value"):
        comment.entity_type = comment.entity_type.value

    return create_item(db, models.Comment, comment, organization_id, user_id)


def update_comment(
    db: Session, comment_id: uuid.UUID, comment: schemas.CommentUpdate, organization_id: str = None, user_id: str = None
) -> Optional[models.Comment]:
    """Update a comment with optimized tenant context"""
    return update_item(db, models.Comment, comment_id, comment, organization_id, user_id)


def delete_comment(db: Session, comment_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[models.Comment]:
    """Delete a comment with optimized tenant context"""
    return delete_item(db, models.Comment, comment_id, organization_id, user_id)


def add_emoji_reaction(
    db: Session, comment_id: uuid.UUID, emoji: str, user_id: uuid.UUID, user_name: str
) -> Optional[models.Comment]:
    """Add an emoji reaction to a comment"""
    comment = get_comment(db, comment_id)
    if not comment:
        return None

    # Initialize emojis if None
    if comment.emojis is None:
        comment.emojis = {}

    # Initialize emoji list if it doesn't exist
    if emoji not in comment.emojis:
        comment.emojis[emoji] = []

    # Check if user already reacted with this emoji
    existing_reaction = next(
        (reaction for reaction in comment.emojis[emoji] if reaction["user_id"] == str(user_id)),
        None,
    )

    if existing_reaction:
        return comment  # User already reacted, no change needed

    # Add new reaction
    new_reaction = {"user_id": str(user_id), "user_name": user_name}

    # Create a completely new emojis dictionary instead of modifying in-place
    current_emojis = dict(comment.emojis) if comment.emojis else {}
    if emoji not in current_emojis:
        current_emojis[emoji] = []
    current_emojis[emoji].append(new_reaction)

    # Convert dictionary to JSON string for PostgreSQL
    emojis_json = json.dumps(current_emojis)

    update_sql = text("UPDATE comment SET emojis = :emojis WHERE id = :comment_id")
    db.execute(update_sql, {"emojis": emojis_json, "comment_id": comment_id})

    db.commit()
    db.refresh(comment)

    return comment


def remove_emoji_reaction(
    db: Session, comment_id: uuid.UUID, emoji: str, user_id: uuid.UUID
) -> Optional[models.Comment]:
    """Remove an emoji reaction from a comment"""
    comment = get_comment(db, comment_id)
    if not comment:
        return None

    if comment.emojis is None or emoji not in comment.emojis:
        return comment  # No reactions to remove

    # Remove user's reaction
    comment.emojis[emoji] = [
        reaction for reaction in comment.emojis[emoji] if reaction["user_id"] != str(user_id)
    ]

    # Remove emoji key if no reactions left
    if not comment.emojis[emoji]:
        del comment.emojis[emoji]

    # Convert dictionary to JSON string for PostgreSQL
    emojis_json = json.dumps(comment.emojis)

    update_sql = text("UPDATE comment SET emojis = :emojis WHERE id = :comment_id")
    db.execute(update_sql, {"emojis": emojis_json, "comment_id": comment_id})

    db.commit()
    db.refresh(comment)

    return comment


# Task CRUD
def get_task(db: Session, task_id: uuid.UUID) -> Optional[models.Task]:
    """Get a single task by ID"""
    return get_item_detail(db, models.Task, task_id)


def get_task_with_comment_count(db: Session, task_id: uuid.UUID) -> Optional[models.Task]:
    """Get a single task by ID with comment count"""
    from sqlalchemy import func

    # Get the task
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        return None

    # Get comment count for this specific task
    comment_count = (
        db.query(func.count(models.Comment.id))
        .filter(models.Comment.entity_id == task_id)
        .filter(models.Comment.entity_type == "Task")
        .scalar()
    ) or 0

    # Add total_comments to the task
    task.total_comments = comment_count

    return task


def get_tasks(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Task]:
    """Get tasks with filtering and sorting"""
    return get_items_detail(db, models.Task, skip, limit, sort_by, sort_order, filter)


def create_task(
    db: Session, task: schemas.TaskCreate, organization_id: str = None, user_id: str = None
) -> models.Task:
    """Create a new task"""
    # Check if task is being created with "Completed" status
    if task.status_id is not None:
        status = db.query(models.Status).filter(models.Status.id == task.status_id).first()
        if status and status.name == "Completed":
            # Set completed_at to current timestamp
            task.completed_at = datetime.utcnow()

    return create_item(db, models.Task, task, organization_id=organization_id, user_id=user_id)


def update_task(db: Session, task_id: uuid.UUID, task: schemas.TaskUpdate) -> Optional[models.Task]:
    """Update a task"""
    # Check if status is being changed to "Completed"
    if task.status_id is not None:
        # Get current task to compare status
        current_task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if current_task and task.status_id != current_task.status_id:
            # Get the new status to check if it's "Completed"
            new_status = db.query(models.Status).filter(models.Status.id == task.status_id).first()
            if new_status and new_status.name == "Completed":
                # Set completed_at to current timestamp
                task.completed_at = datetime.utcnow()

    return update_item(db, models.Task, task_id, task)


def delete_task(db: Session, task_id: uuid.UUID) -> bool:
    """Delete a task"""
    result = delete_item(db, models.Task, task_id)
    return result is not None


def get_tasks_with_comment_counts(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str = None,
) -> List[models.Task]:
    """
    Get tasks with comment counts using PostgreSQL aggregation.
    Uses a subquery to count comments for each task efficiently.
    """
    from sqlalchemy import func, select
    from sqlalchemy.orm import aliased

    # Create alias for Comment model
    Comment = aliased(models.Comment)

    # Subquery to count comments for each task
    comment_count_subquery = (
        select(Comment.entity_id, func.count(Comment.id).label("total_comments"))
        .where(Comment.entity_type == "Task")
        .group_by(Comment.entity_id)
        .subquery()
    )

    # First get the tasks with organization filter
    from rhesis.backend.app.utils.model_utils import apply_organization_filter

    base_query = db.query(models.Task)
    base_query = apply_organization_filter(db, base_query, models.Task)

    # Apply OData filter if provided
    if filter:
        from rhesis.backend.app.utils.odata import apply_odata_filter

        base_query = apply_odata_filter(base_query, models.Task, filter)

    # Apply sorting
    sort_column = getattr(models.Task, sort_by, models.Task.created_at)
    if sort_order.lower() == "desc":
        base_query = base_query.order_by(sort_column.desc())
    else:
        base_query = base_query.order_by(sort_column.asc())

    # Apply pagination
    base_query = base_query.offset(skip).limit(limit)

    # Execute the base query to get tasks
    tasks = base_query.all()

    # Now get comment counts for these tasks
    task_ids = [task.id for task in tasks]

    if task_ids:
        # Get comment counts for the tasks
        comment_counts = (
            db.query(Comment.entity_id, func.count(Comment.id).label("total_comments"))
            .where(Comment.entity_type == "Task")
            .where(Comment.entity_id.in_(task_ids))
            .group_by(Comment.entity_id)
            .all()
        )

        # Create a mapping of task_id to comment count
        comment_count_map = {str(task_id): count for task_id, count in comment_counts}
    else:
        comment_count_map = {}

    # Add total_comments to each task
    for task in tasks:
        task.total_comments = comment_count_map.get(str(task.id), 0)

    return tasks

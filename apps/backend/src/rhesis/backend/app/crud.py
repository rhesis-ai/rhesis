"""
This code implements the CRUD operations for the models in the application.
"""

import uuid
from typing import List, Optional, Union
from uuid import UUID
from datetime import datetime, timezone

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
def get_endpoint(db: Session, endpoint_id: uuid.UUID) -> Optional[models.Endpoint]:
    return get_item(db, models.Endpoint, endpoint_id)


def get_endpoints(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Endpoint]:
    return get_items_detail(db, models.Endpoint, skip, limit, sort_by, sort_order, filter)


def create_endpoint(db: Session, endpoint: schemas.EndpointCreate) -> models.Endpoint:
    return create_item(db, models.Endpoint, endpoint)


def update_endpoint(
    db: Session, endpoint_id: uuid.UUID, endpoint: schemas.EndpointUpdate
) -> Optional[models.Endpoint]:
    return update_item(db, models.Endpoint, endpoint_id, endpoint)


def delete_endpoint(db: Session, endpoint_id: uuid.UUID) -> Optional[models.Endpoint]:
    return delete_item(db, models.Endpoint, endpoint_id)


# UseCase CRUD
def get_use_case(db: Session, use_case_id: uuid.UUID) -> Optional[models.UseCase]:
    return get_item(db, models.UseCase, use_case_id)


def get_use_cases(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.UseCase]:
    return get_items(db, models.UseCase, skip, limit, sort_by, sort_order, filter)


def create_use_case(db: Session, use_case: schemas.UseCaseCreate) -> models.UseCase:
    return create_item(db, models.UseCase, use_case)


def update_use_case(
    db: Session, use_case_id: uuid.UUID, use_case: schemas.UseCaseUpdate
) -> Optional[models.UseCase]:
    return update_item(db, models.UseCase, use_case_id, use_case)


def delete_use_case(db: Session, use_case_id: uuid.UUID) -> Optional[models.UseCase]:
    return delete_item(db, models.UseCase, use_case_id)


# Prompt CRUD
def get_prompt(db: Session, prompt_id: uuid.UUID) -> Optional[models.Prompt]:
    return get_item(db, models.Prompt, prompt_id)


def get_prompts(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Prompt]:
    return get_items(db, models.Prompt, skip, limit, sort_by, sort_order, filter)


def create_prompt(db: Session, prompt: schemas.PromptCreate) -> models.Prompt:
    return create_item(db, models.Prompt, prompt)


def update_prompt(
    db: Session, prompt_id: uuid.UUID, prompt: schemas.PromptUpdate
) -> Optional[models.Prompt]:
    return update_item(db, models.Prompt, prompt_id, prompt)


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
    db: Session, prompt_template: schemas.PromptTemplateCreate
) -> models.PromptTemplate:
    return create_item(db, models.PromptTemplate, prompt_template)


def update_prompt_template(
    db: Session, prompt_template_id: uuid.UUID, prompt_template: schemas.PromptTemplateUpdate
) -> Optional[models.PromptTemplate]:
    return update_item(db, models.PromptTemplate, prompt_template_id, prompt_template)


def delete_prompt_template(
    db: Session, prompt_template_id: uuid.UUID
) -> Optional[models.PromptTemplate]:
    return delete_item(db, models.PromptTemplate, prompt_template_id)


# Category CRUD
def get_category(db: Session, category_id: uuid.UUID) -> Optional[models.Category]:
    return get_item(db, models.Category, category_id)


def get_categories(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Category]:
    return get_items(db, models.Category, skip, limit, sort_by, sort_order, filter)


def create_category(db: Session, category: schemas.CategoryCreate) -> models.Category:
    return create_item(db, models.Category, category)


def update_category(
    db: Session, category_id: uuid.UUID, category: schemas.CategoryUpdate
) -> Optional[models.Category]:
    return update_item(db, models.Category, category_id, category)


def delete_category(db: Session, category_id: uuid.UUID) -> Optional[models.Category]:
    return delete_item(db, models.Category, category_id)


# Behavior CRUD
def get_behavior(db: Session, behavior_id: uuid.UUID) -> Optional[models.Behavior]:
    return get_item(db, models.Behavior, behavior_id)


def get_behaviors(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Behavior]:
    return get_items(db, models.Behavior, skip, limit, sort_by, sort_order, filter)


def create_behavior(db: Session, behavior: schemas.BehaviorCreate) -> models.Behavior:
    return create_item(db, models.Behavior, behavior)


def update_behavior(
    db: Session, behavior_id: uuid.UUID, behavior: schemas.BehaviorUpdate
) -> Optional[models.Behavior]:
    return update_item(db, models.Behavior, behavior_id, behavior)


def delete_behavior(db: Session, behavior_id: uuid.UUID) -> Optional[models.Behavior]:
    return delete_item(db, models.Behavior, behavior_id)


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
    db: Session, response_pattern: schemas.ResponsePatternCreate
) -> models.ResponsePattern:
    return create_item(db, models.ResponsePattern, response_pattern)


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
) -> List[models.TestSet]:
    """
    Get test sets with detail loading and proper filtering.
    Public test sets are visible regardless of organization.
    """
    return (
        QueryBuilder(db, models.TestSet)
        .with_joinedloads()
        .with_visibility_filter()  # This already handles public visibility correctly
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def create_test_set(db: Session, test_set: schemas.TestSetCreate) -> models.TestSet:
    return create_item(db, models.TestSet, test_set)


def update_test_set(
    db: Session, test_set_id: uuid.UUID, test_set: schemas.TestSetUpdate
) -> Optional[models.TestSet]:
    return update_item(db, models.TestSet, test_set_id, test_set)


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
) -> Optional[models.TestConfiguration]:
    return update_item(db, models.TestConfiguration, test_configuration_id, test_configuration)


# Risk CRUD
def get_risk(db: Session, risk_id: uuid.UUID) -> Optional[models.Risk]:
    return get_item(db, models.Risk, risk_id)


def get_risks(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Risk]:
    return get_items(db, models.Risk, skip, limit, sort_by, sort_order, filter)


def create_risk(db: Session, risk: schemas.RiskCreate) -> models.Risk:
    return create_item(db, models.Risk, risk)


def update_risk(db: Session, risk_id: uuid.UUID, risk: schemas.RiskUpdate) -> Optional[models.Risk]:
    return update_item(db, models.Risk, risk_id, risk)


# Status CRUD
def get_status(db: Session, status_id: uuid.UUID) -> Optional[models.Status]:
    return get_item(db, models.Status, status_id)


def get_statuses(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Status]:
    return get_items(db, models.Status, skip, limit, sort_by, sort_order, filter)


def create_status(db: Session, status: schemas.StatusCreate) -> models.Status:
    return create_item(db, models.Status, status)


def update_status(
    db: Session, status_id: uuid.UUID, status: schemas.StatusUpdate
) -> Optional[models.Status]:
    return update_item(db, models.Status, status_id, status)


# Source CRUD
def get_source(db: Session, source_id: uuid.UUID) -> Optional[models.Source]:
    return get_item(db, models.Source, source_id)


def get_sources(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Source]:
    return get_items(db, models.Source, skip, limit, sort_by, sort_order, filter)


def create_source(db: Session, source: schemas.SourceCreate) -> models.Source:
    return create_item(db, models.Source, source)


def update_source(
    db: Session, source_id: uuid.UUID, source: schemas.SourceUpdate
) -> Optional[models.Source]:
    return update_item(db, models.Source, source_id, source)


# Topic CRUD
def get_topic(db: Session, topic_id: uuid.UUID) -> Optional[models.Topic]:
    return get_item(db, models.Topic, topic_id)


def get_topics(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Topic]:
    return get_items(db, models.Topic, skip, limit, sort_by, sort_order, filter)


def create_topic(db: Session, topic: schemas.TopicCreate) -> models.Topic:
    return create_item(db, models.Topic, topic)


def update_topic(
    db: Session, topic_id: uuid.UUID, topic: schemas.TopicUpdate
) -> Optional[models.Topic]:
    return update_item(db, models.Topic, topic_id, topic)


def delete_topic(db: Session, topic_id: uuid.UUID) -> Optional[models.Topic]:
    return delete_item(db, models.Topic, topic_id)


# Demographic CRUD
def get_demographic(db: Session, demographic_id: uuid.UUID) -> Optional[models.Demographic]:
    return get_item(db, models.Demographic, demographic_id)


def get_demographics(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Demographic]:
    return get_items(db, models.Demographic, skip, limit, sort_by, sort_order, filter)


def create_demographic(db: Session, demographic: schemas.DemographicCreate) -> models.Demographic:
    return create_item(db, models.Demographic, demographic)


def update_demographic(
    db: Session, demographic_id: uuid.UUID, demographic: schemas.DemographicUpdate
) -> Optional[models.Demographic]:
    return update_item(db, models.Demographic, demographic_id, demographic)


# Dimension CRUD
def get_dimension(db: Session, dimension_id: uuid.UUID) -> Optional[models.Dimension]:
    return get_item(db, models.Dimension, dimension_id)


def get_dimensions(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Dimension]:
    return get_items(db, models.Dimension, skip, limit, sort_by, sort_order, filter)


def create_dimension(db: Session, dimension: schemas.DimensionCreate) -> models.Dimension:
    return create_item(db, models.Dimension, dimension)


def update_dimension(
    db: Session, dimension_id: uuid.UUID, dimension: schemas.DimensionUpdate
) -> Optional[models.Dimension]:
    return update_item(db, models.Dimension, dimension_id, dimension)


# User CRUD
def get_user(db: Session, user_id: uuid.UUID) -> Optional[models.User]:
    return get_item(db, models.User, user_id)


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
    db_user = models.User(**user.dict())
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
def get_tag(db: Session, tag_id: uuid.UUID) -> Optional[models.Tag]:
    return get_item(db, models.Tag, tag_id)


def get_tags(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Tag]:
    return get_items(db, models.Tag, skip, limit, sort_by, sort_order, filter)


def create_tag(db: Session, tag: schemas.TagCreate) -> models.Tag:
    return create_item(db, models.Tag, tag)


def update_tag(db: Session, tag_id: uuid.UUID, tag: schemas.TagUpdate) -> Optional[models.Tag]:
    return update_item(db, models.Tag, tag_id, tag)


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
def get_token(db: Session, token_id: uuid.UUID) -> Optional[models.Token]:
    return get_item(db, models.Token, token_id)


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
    query_builder = QueryBuilder(db, models.Token).with_organization_filter().with_custom_filter(
        lambda q: q.filter(models.Token.user_id == user_id, models.Token.token_type == "bearer")
    )
    
    # Add validity check if requested
    if valid_only:
        now = datetime.now(timezone.utc)
        query_builder = query_builder.with_custom_filter(
            lambda q: q.filter(
                # Token is either never-expiring (expires_at is None) or not yet expired
                (models.Token.expires_at == None) | (models.Token.expires_at > now)
            )
        )
    
    return (
        query_builder
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def create_token(db: Session, token: schemas.TokenCreate) -> models.Token:
    return create_item(db, models.Token, token)


def update_token(
    db: Session, token_id: uuid.UUID, token: schemas.TokenUpdate
) -> Optional[models.Token]:
    return update_item(db, models.Token, token_id, token)


def revoke_token(db: Session, token_id: uuid.UUID) -> Optional[models.Token]:
    return delete_item(db, models.Token, token_id)


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
def get_organization(db: Session, organization_id: uuid.UUID) -> Optional[models.Organization]:
    return get_item(db, models.Organization, organization_id)


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


# Project CRUD
def get_project(db: Session, project_id: uuid.UUID) -> Optional[models.Project]:
    return get_item(db, models.Project, project_id)


def get_projects(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Project]:
    return get_items_detail(db, models.Project, skip, limit, sort_by, sort_order, filter)


def create_project(db: Session, project: schemas.ProjectCreate) -> models.Project:
    return create_item(db, models.Project, project)


def update_project(
    db: Session, project_id: uuid.UUID, project: schemas.ProjectUpdate
) -> Optional[models.Project]:
    return update_item(db, models.Project, project_id, project)


def get_test(db: Session, test_id: uuid.UUID) -> Optional[models.Test]:
    return get_item_detail(db, models.Test, test_id)


def get_tests(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Test]:
    return get_items_detail(db, models.Test, skip, limit, sort_by, sort_order, filter)


def create_test(db: Session, test: schemas.TestCreate) -> models.Test:
    return create_item(db, models.Test, test)


def update_test(db: Session, test_id: uuid.UUID, test: schemas.TestUpdate) -> Optional[models.Test]:
    return update_item(db, models.Test, test_id, test)


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
            test_test_set_association.select().where(
                test_test_set_association.c.test_id == test_id
            )
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
def get_test_context(db: Session, test_context_id: uuid.UUID) -> Optional[models.TestContext]:
    return get_item(db, models.TestContext, test_context_id)


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


def create_test_context(db: Session, test_context: schemas.TestContextCreate) -> models.TestContext:
    return create_item(db, models.TestContext, test_context)


def update_test_context(
    db: Session, test_context_id: uuid.UUID, test_context: schemas.TestContextUpdate
) -> Optional[models.TestContext]:
    return update_item(db, models.TestContext, test_context_id, test_context)


def delete_test_context(db: Session, test_context_id: uuid.UUID) -> Optional[models.TestContext]:
    return delete_item(db, models.TestContext, test_context_id)


# Test Run CRUD
def get_test_run(db: Session, test_run_id: uuid.UUID) -> Optional[models.TestRun]:
    return get_item_detail(db, models.TestRun, test_run_id)


def get_test_runs(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.TestRun]:
    return get_items_detail(db, models.TestRun, skip, limit, sort_by, sort_order, filter)


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
                test_run_dict = test_run.model_dump() if hasattr(test_run, 'model_dump') else test_run.dict()
                test_run_dict['name'] = generated_name
                test_run = schemas.TestRunCreate(**test_run_dict)
            except Exception as e:
                logger.warning(f"Failed to generate memorable name: {e}. Using fallback.")
                # Fallback to a simple timestamp-based name
                import time
                timestamp = int(time.time())
                test_run_dict = test_run.model_dump() if hasattr(test_run, 'model_dump') else test_run.dict()
                test_run_dict['name'] = f"test-run-{timestamp}"
                test_run = schemas.TestRunCreate(**test_run_dict)
        else:
            logger.warning("No organization_id available for test run name generation")
    
    return create_item(db, models.TestRun, test_run)


def update_test_run(
    db: Session, test_run_id: uuid.UUID, test_run: schemas.TestRunUpdate
) -> Optional[models.TestRun]:
    return update_item(db, models.TestRun, test_run_id, test_run)


def delete_test_run(db: Session, test_run_id: uuid.UUID) -> Optional[models.TestRun]:
    return delete_item(db, models.TestRun, test_run_id)


# Test Result CRUD
def get_test_result(db: Session, test_result_id: uuid.UUID) -> Optional[models.TestResult]:
    return get_item(db, models.TestResult, test_result_id)


def get_test_results(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.TestResult]:
    return get_items(db, models.TestResult, skip, limit, sort_by, sort_order, filter)


def create_test_result(db: Session, test_result: schemas.TestResultCreate) -> models.TestResult:
    return create_item(db, models.TestResult, test_result)


def update_test_result(
    db: Session, test_result_id: uuid.UUID, test_result: schemas.TestResultUpdate
) -> Optional[models.TestResult]:
    return update_item(db, models.TestResult, test_result_id, test_result)


def delete_test_result(db: Session, test_result_id: uuid.UUID) -> Optional[models.TestResult]:
    return delete_item(db, models.TestResult, test_result_id)


def delete_project(db: Session, project_id: uuid.UUID) -> Optional[models.Project]:
    return delete_item(db, models.Project, project_id)


# TypeLookup CRUD
def get_type_lookup(db: Session, type_lookup_id: uuid.UUID) -> Optional[models.TypeLookup]:
    return get_item(db, models.TypeLookup, type_lookup_id)


def get_type_lookups(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.TypeLookup]:
    return get_items(db, models.TypeLookup, skip, limit, sort_by, sort_order, filter)


def create_type_lookup(db: Session, type_lookup: schemas.TypeLookupCreate) -> models.TypeLookup:
    return create_item(db, models.TypeLookup, type_lookup)


def update_type_lookup(
    db: Session, type_lookup_id: uuid.UUID, type_lookup: schemas.TypeLookupUpdate
) -> Optional[models.TypeLookup]:
    return update_item(db, models.TypeLookup, type_lookup_id, type_lookup)


def delete_type_lookup(db: Session, type_lookup_id: uuid.UUID) -> Optional[models.TypeLookup]:
    return delete_item(db, models.TypeLookup, type_lookup_id)


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
    """Get a specific metric by ID with its related objects"""
    return get_item_detail(db, models.Metric, metric_id)


def get_metrics(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
) -> List[models.Metric]:
    """Get all metrics with their related objects"""
    return get_items_detail(db, models.Metric, skip, limit, sort_by, sort_order, filter)


def create_metric(db: Session, metric: schemas.MetricCreate) -> models.Metric:
    """Create a new metric"""
    return create_item(db, models.Metric, metric)


def update_metric(
    db: Session, metric_id: uuid.UUID, metric: schemas.MetricUpdate
) -> Optional[models.Metric]:
    """Update a metric"""
    return update_item(db, models.Metric, metric_id, metric)


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
    limit: int = 10,
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
    limit: int = 10,
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


def create_model(db: Session, model: schemas.ModelCreate) -> models.Model:
    """Create a new model"""
    return create_item(db, models.Model, model)


def update_model(
    db: Session, model_id: uuid.UUID, model: schemas.ModelUpdate
) -> Optional[models.Model]:
    """Update a model"""
    return update_item(db, models.Model, model_id, model)


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

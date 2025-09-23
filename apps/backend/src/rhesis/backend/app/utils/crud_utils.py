"""
Utility functions for CRUD operations with improved readability and maintainability.
"""

import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import EntityType
# Removed unused imports - legacy tenant functions no longer needed
from rhesis.backend.app.models import Behavior, Category, Status, Topic, TypeLookup
from rhesis.backend.app.utils.model_utils import QueryBuilder
from rhesis.backend.logging import logger

# Define a generic type variable
T = TypeVar("T")

# Common field names for entity identification
IDENTIFYING_FIELDS = ["name", "code", "external_id", "slug", "nano_id"]
UUID_FIELD_PATTERNS = ["UUID", "GUID", "uuid"]


def _convert_pydantic_to_dict(item_data: Union[Dict[str, Any], BaseModel]) -> Dict[str, Any]:
    """Convert Pydantic models to dictionary format."""
    if hasattr(item_data, "model_dump"):
        return item_data.model_dump()
    elif hasattr(item_data, "dict"):  # For older Pydantic versions
        return item_data.dict()
    return item_data


def _convert_pydantic_to_dict_exclude_unset(
    item_data: Union[Dict[str, Any], BaseModel],
) -> Dict[str, Any]:
    """Convert Pydantic models to dictionary format, excluding unset fields."""
    if hasattr(item_data, "model_dump"):
        return item_data.model_dump(exclude_unset=True)
    elif hasattr(item_data, "dict"):  # For older Pydantic versions
        return item_data.dict(exclude_unset=True)
    return item_data


def _is_uuid_field(model: Type[T], field_name: str) -> bool:
    """Check if a field is a UUID/GUID field."""
    if not hasattr(model, field_name):
        return False

    column = getattr(model, field_name)
    if not hasattr(column, "type"):
        return False

    field_type = str(column.type)
    return any(pattern in field_type for pattern in UUID_FIELD_PATTERNS) or field_name.endswith(
        "_id"
    )


def _clean_uuid_fields(model: Type[T], item_data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up empty string values for UUID fields to prevent database errors."""
    cleaned_data = item_data.copy()

    for field_name, field_value in list(cleaned_data.items()):
        if field_value == "" and _is_uuid_field(model, field_name):
            cleaned_data[field_name] = None

    return cleaned_data


def _auto_populate_tenant_fields(model: Type[T], item_data: Dict[str, Any], organization_id: str = None, user_id: str = None) -> Dict[str, Any]:
    """
    Auto-populate organization_id and user_id using directly provided values.
    
    OPTIMIZED VERSION: Completely bypasses database queries and session variables.
    This eliminates ALL delays by directly using provided tenant context.
    """
    columns = inspect(model).columns.keys()
    populated_data = item_data.copy()

    logger.debug(f"_auto_populate_tenant_fields - model: {model.__name__}, input data: {item_data}")
    
    # Auto-populate organization_id (direct - no DB queries, no session variables!)
    if "organization_id" in columns and not populated_data.get("organization_id") and organization_id:
        try:
            org_uuid = UUID(organization_id)
            populated_data["organization_id"] = org_uuid
            logger.debug(f"_auto_populate_tenant_fields - Auto-populating organization_id: '{org_uuid}' (direct)")
        except (ValueError, TypeError) as e:
            logger.debug(f"_auto_populate_tenant_fields - Invalid organization_id: {organization_id}, error: {e}")
    
    # Auto-populate user_id (direct - no DB queries, no session variables!)
    if "user_id" in columns and not populated_data.get("user_id") and user_id:
        try:
            user_uuid = UUID(user_id)
            populated_data["user_id"] = user_uuid
            logger.debug(f"_auto_populate_tenant_fields - Auto-populating user_id: '{user_uuid}' (direct)")
        except (ValueError, TypeError) as e:
            logger.debug(f"_auto_populate_tenant_fields - Invalid user_id: {user_id}, error: {e}")
    
    logger.debug(f"_auto_populate_tenant_fields - Final populated data: {populated_data}")
    return populated_data


def _prepare_item_data(model: Type[T], item_data: Union[Dict[str, Any], BaseModel], organization_id: str = None, user_id: str = None) -> Dict[str, Any]:
    """
    Prepare item data for database operations using directly provided tenant context.
    
    OPTIMIZED VERSION: Completely bypasses database queries and session variables.
    """
    # Convert Pydantic to dict
    data = _convert_pydantic_to_dict(item_data)

    # Clean UUID fields
    data = _clean_uuid_fields(model, data)
    
    # Auto-populate tenant fields using direct values
    data = _auto_populate_tenant_fields(model, data, organization_id, user_id)
    
    return data




def _prepare_update_data(db: Session, model: Type[T], item_data: Union[Dict[str, Any], BaseModel]) -> Dict[str, Any]:
    """Prepare item data for update operations."""
    # Convert Pydantic to dict (excluding unset fields for updates)
    data = _convert_pydantic_to_dict_exclude_unset(item_data)

    # Clean UUID fields
    data = _clean_uuid_fields(model, data)

    return data


def _create_db_item_with_transaction(
    db: Session, model: Type[T], item_data: Dict[str, Any], commit: bool = True
) -> T:
    """Create database item within a transaction."""
    db_item = model(**item_data)

    db.add(db_item)
    db.flush()  # Flush to get the ID and other generated values
    db.refresh(db_item)  # Refresh to ensure we have all generated values

    if commit:
        db.commit()

    return db_item


# ============================================================================
# Core CRUD Operations
# ============================================================================

def get_item(db: Session, model: Type[T], item_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[T]:
    """
    Get a single item by ID with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    return (
        QueryBuilder(db, model)
        .with_organization_filter(organization_id)
        .with_visibility_filter()
        .filter_by_id(item_id)
    )


def get_item_detail(db: Session, model: Type[T], item_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[T]:
    """
    Get a single item with all relationships loaded using optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    return (
        QueryBuilder(db, model)
        .with_joinedloads()
        .with_organization_filter(organization_id)
        .with_visibility_filter()
        .filter_by_id(item_id)
    )


def get_items(
    db: Session,
    model: Type[T],
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[T]:
    """
    Get multiple items with pagination, sorting, and filtering using optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    return (
        QueryBuilder(db, model)
        .with_organization_filter(organization_id)
        .with_visibility_filter()
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def get_items_detail(
    db: Session,
    model: Type[T],
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    nested_relationships: dict = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[T]:
    """
    Get multiple items with optimized relationship loading using optimized approach - no session variables needed.
    Uses selectinload for many-to-many relationships to avoid cartesian products.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    
    Args:
        nested_relationships: Dict specifying nested relationships to load.
                            Format: {"relationship_name": ["nested_rel1", "nested_rel2"]}
    """
    return (
        QueryBuilder(db, model)
        .with_optimized_loads(
            skip_many_to_many=False, 
            skip_one_to_many=True, 
            nested_relationships=nested_relationships
        )
        .with_organization_filter(organization_id)
        .with_visibility_filter()
        .with_odata_filter(filter)
        .with_pagination(skip, limit)
        .with_sorting(sort_by, sort_order)
        .all()
    )


def create_item(db: Session, model: Type[T], item_data: Union[Dict[str, Any], BaseModel], organization_id: str = None, user_id: str = None, commit: bool = True) -> T:
    """
    Create a new item with optimized approach - no session variables needed.
    
    OPTIMIZED VERSION: Completely bypasses database queries and session variables.
    This reduces creation time significantly by directly providing tenant context.
    
    Args:
        db: Database session (regular SessionLocal)
        model: SQLAlchemy model class
        item_data: Item data as dict or Pydantic model
        organization_id: Organization ID to use directly (bypasses session variables)
        user_id: User ID to use directly (bypasses session variables)
        commit: Whether to commit the transaction (default: True)

    Returns:
        Created database item
    """
    # Prepare data for creation using direct tenant context
    prepared_data = _prepare_item_data(model, item_data, organization_id, user_id)
    
    # Create item directly without session variable overhead
    return _create_db_item_with_transaction(db, model, prepared_data, commit=commit)



def update_item(
    db: Session,
    model: Type[T],
    item_id: uuid.UUID,
    item_data: Union[Dict[str, Any], BaseModel],
    organization_id: str = None,
    user_id: str = None,
) -> Optional[T]:
    """
    Update an existing item with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        item_id: ID of item to update
        item_data: Updated item data as dict or Pydantic model
        organization_id: Direct organization ID for tenant context
        user_id: Direct user ID for tenant context
        
    Returns:
        Updated database item or None if not found
    """
    # Get existing item with direct tenant context
    db_item = get_item(db, model, item_id, organization_id, user_id)
    if db_item is None:
        return None

    # Prepare update data with tenant context
    update_data = _prepare_update_data(db, model, item_data)
    
    # Auto-populate tenant fields if provided (for updates that should update these fields)
    if organization_id is not None:
        columns = inspect(model).columns.keys()
        if "organization_id" in columns:
            try:
                update_data["organization_id"] = UUID(organization_id)
                logger.debug(f"update_item - Auto-populating organization_id: '{organization_id}' for update")
            except (ValueError, TypeError) as e:
                logger.debug(f"update_item - Invalid organization_id: {organization_id}, error: {e}")
    
    if user_id is not None:
        columns = inspect(model).columns.keys()
        if "user_id" in columns:
            try:
                update_data["user_id"] = UUID(user_id)
                logger.debug(f"update_item - Auto-populating user_id: '{user_id}' for update")
            except (ValueError, TypeError) as e:
                logger.debug(f"update_item - Invalid user_id: {user_id}, error: {e}")

    # Apply updates
    for key, value in update_data.items():
        if hasattr(db_item, key):
            setattr(db_item, key, value)

    # Commit changes
    db.flush()
    db.refresh(db_item)
    db.commit()
    
    return db_item


def delete_item(db: Session, model: Type[T], item_id: uuid.UUID, organization_id: str = None, user_id: str = None) -> Optional[T]:
    """
    Delete an item and return the deleted item with optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        item_id: ID of item to delete
        organization_id: Direct organization ID for tenant context
        user_id: Direct user ID for tenant context
        
    Returns:
        Deleted database item or None if not found
    """
    # Get existing item with direct tenant context
    db_item = get_item(db, model, item_id, organization_id, user_id)
    if db_item is None:
        return None

    # Store reference before deletion
    deleted_item = db_item

    # Delete and commit
    db.delete(db_item)
    db.commit()
    
    return deleted_item


def count_items(db: Session, model: Type[T], filter: str = None, organization_id: str = None, user_id: str = None) -> int:
    """
    Get the total count of items matching filters (without pagination) using optimized approach - no session variables needed.
    
    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during counting
    - Direct tenant context injection
    """
    return (
        QueryBuilder(db, model)
        .with_organization_filter(organization_id)
        .with_visibility_filter()
        .with_odata_filter(filter)
        .count()
    )


# ============================================================================
# Advanced CRUD Operations
# ============================================================================


def _build_search_filters_for_model(model: Type[T], search_data: Dict[str, Any]) -> List:
    """Build search filters based on model type and search data."""
    search_filters = []
    columns = inspect(model).columns.keys()

    # Always include organization_id in search if available
    if "organization_id" in columns and "organization_id" in search_data:
        search_filters.append(getattr(model, "organization_id") == search_data["organization_id"])

    # Handle model-specific identifying fields
    if model.__name__ == "TypeLookup":
        # TypeLookup requires both type_name and type_value
        if "type_name" in search_data and "type_value" in search_data:
            search_filters.extend(
                [
                    model.type_name == search_data["type_name"],
                    model.type_value == search_data["type_value"],
                ]
            )
    elif hasattr(model, "content"):
        # Models using content as identifier
        if "content" in search_data:
            search_filters.append(model.content == search_data["content"])

        # For Prompt models, also consider expected_response as part of the unique identifier
        # This prevents reusing prompts with same content but different expected responses
        if model.__name__ == "Prompt" and "expected_response" in search_data:
            # Handle both None and actual string values for expected_response
            expected_response = search_data["expected_response"]
            if expected_response is None:
                search_filters.append(model.expected_response.is_(None))
            else:
                search_filters.append(model.expected_response == expected_response)
    else:
        # Standard models using common identifying fields
        for field in IDENTIFYING_FIELDS:
            if field in search_data and field in columns and search_data[field]:
                search_filters.append(getattr(model, field) == search_data[field])

    return search_filters


def get_or_create_entity(
    db: Session, model: Type[T], entity_data: Union[Dict[str, Any], BaseModel], organization_id: str = None, user_id: str = None, commit: bool = True
) -> T:
    """
    Get or create an entity based on identifying fields using optimized approach - no session variables needed.

    Attempts to find an existing entity using unique identifying fields before creating a new one.
    Always includes organization_id in the lookup if the model supports it.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during lookup/creation
    - Direct tenant context injection

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_data: Entity data as dict or Pydantic model
        organization_id: Direct organization ID for tenant context
        user_id: Direct user ID for tenant context
        commit: Whether to commit the transaction when creating (default: True)

    Returns:
        Existing or newly created entity
    """
    # Convert to dict for processing
    search_data = _convert_pydantic_to_dict(entity_data)

    # Build base query with direct tenant context
    query = QueryBuilder(db, model).with_organization_filter(organization_id).with_visibility_filter()

    # Try to find by ID first if provided
    if "id" in search_data and search_data["id"]:
        search_filters = _build_search_filters_for_model(model, search_data)
        db_entity = query.with_custom_filter(
            lambda q: q.filter(model.id == search_data["id"], *search_filters)
        ).first()
        if db_entity:
            return db_entity

    # Build search filters for other identifying fields
    search_filters = _build_search_filters_for_model(model, search_data)

    # Search for existing entity if we have sufficient filters
    # The base query already includes organization filtering, so we just need identifying fields
    if len(search_filters) >= 1:  # Need at least one identifying field
        db_entity = query.with_custom_filter(lambda q: q.filter(*search_filters)).first()
        if db_entity:
            return db_entity

    # Create new entity if not found using direct tenant context
    return create_item(db, model, entity_data, organization_id, user_id, commit=commit)


# ============================================================================
# Specialized Helper Functions
# ============================================================================


def get_or_create_status(db: Session, name: str, entity_type, description: str = None, organization_id: str = None, user_id: str = None, commit: bool = True) -> Status:
    """Get or create a status with the specified name, entity type, and optional description using optimized approach - no session variables needed."""
    # Handle EntityType enum or string
    entity_type_value = entity_type.value if hasattr(entity_type, "value") else entity_type

    # Get or create the entity type lookup
    entity_type_lookup = get_or_create_type_lookup(
        db=db, type_name="EntityType", type_value=entity_type_value, organization_id=organization_id, user_id=user_id, commit=commit
    )

    # Try to find existing status
    query = (
        QueryBuilder(db, Status)
        .with_organization_filter(organization_id)
        .with_visibility_filter()
        .with_custom_filter(
            lambda q: q.filter(Status.name == name, Status.entity_type_id == entity_type_lookup.id)
        )
    )

    existing_status = query.first()
    if existing_status:
        return existing_status

    # Prepare status data
    status_data = {"name": name, "entity_type_id": entity_type_lookup.id}
    
    # Add description only if provided
    if description is not None:
        status_data["description"] = description

    # Create new status
    return create_item(
        db=db,
        model=Status,
        item_data=status_data,
        organization_id=organization_id,
        user_id=user_id,
        commit=commit,
    )


def get_or_create_type_lookup(
    db: Session, type_name: str, type_value: str, organization_id: str = None, user_id: str = None, commit: bool = True
) -> TypeLookup:
    """Get or create a type lookup with the specified type_name and type_value using optimized approach - no session variables needed."""
    logger.debug(
        f"get_or_create_type_lookup - Looking for type_name='{type_name}', type_value='{type_value}'"
    )

    # Try to find existing type lookup
    query = (
        QueryBuilder(db, TypeLookup)
        .with_organization_filter(organization_id)
        .with_visibility_filter()
        .with_custom_filter(
            lambda q: q.filter(
                TypeLookup.type_name == type_name, TypeLookup.type_value == type_value
            )
        )
    )

    logger.debug("get_or_create_type_lookup - About to execute query for existing type")
    try:
        existing_type = query.first()
        if existing_type:
            logger.debug(f"get_or_create_type_lookup - Found existing type: {existing_type}")
            return existing_type
    except Exception as query_error:
        logger.error(f"get_or_create_type_lookup - Error querying existing type: {query_error}")
        raise

    # Create new type lookup
    logger.debug("get_or_create_type_lookup - Creating new type lookup")
    try:
        result = create_item(
            db=db,
            model=TypeLookup,
            item_data={"type_name": type_name, "type_value": type_value},
            organization_id=organization_id,
            user_id=user_id,
            commit=commit,
        )
        logger.debug(f"get_or_create_type_lookup - Created new type: {result}")
        return result
    except Exception as create_error:
        logger.error(f"get_or_create_type_lookup - Error creating new type: {create_error}")
        raise


def get_or_create_topic(
    db: Session,
    name: str,
    entity_type: str | None = None,
    description: str | None = None,
    status: str | None = None,
    organization_id: str = None,
    user_id: str = None,
    commit: bool = True,
) -> Topic:
    """Get or create a topic with optional entity type, description, and status using optimized approach - no session variables needed."""
    # Prepare topic data - only include non-None values
    topic_data = {"name": name}

    # Add description only if provided
    if description is not None:
        topic_data["description"] = description

    # Add entity type if provided
    if entity_type:
        entity_type_lookup = get_or_create_type_lookup(
            db=db, type_name="EntityType", type_value=entity_type, 
            organization_id=organization_id, user_id=user_id, commit=commit
        )
        topic_data["entity_type_id"] = entity_type_lookup.id

    # Add status if provided
    if status:
        status_obj = get_or_create_status(
            db=db, name=status, entity_type=EntityType.GENERAL, 
            organization_id=organization_id, user_id=user_id, commit=commit
        )
        topic_data["status_id"] = status_obj.id

    # Use get_or_create_entity for consistent lookup logic
    return get_or_create_entity(db, Topic, topic_data, organization_id, user_id, commit=commit)


def get_or_create_category(
    db: Session,
    name: str,
    entity_type: str | None = None,
    description: str | None = None,
    status: str | None = None,
    organization_id: str = None,
    user_id: str = None,
    commit: bool = True,
) -> Category:
    """Get or create a category with optional entity type, description, and status using optimized approach - no session variables needed."""
    # Prepare category data - only include non-None values
    category_data = {"name": name}

    # Add description only if provided
    if description is not None:
        category_data["description"] = description

    # Add entity type if provided
    if entity_type:
        entity_type_lookup = get_or_create_type_lookup(
            db=db, type_name="EntityType", type_value=entity_type, 
            organization_id=organization_id, user_id=user_id, commit=commit
        )
        category_data["entity_type_id"] = entity_type_lookup.id

    # Add status if provided
    if status:
        status_obj = get_or_create_status(
            db=db, name=status, entity_type=EntityType.GENERAL, 
            organization_id=organization_id, user_id=user_id, commit=commit
        )
        category_data["status_id"] = status_obj.id

    # Use get_or_create_entity for consistent lookup logic
    return get_or_create_entity(db, Category, category_data, organization_id, user_id, commit=commit)


def get_or_create_behavior(
    db: Session,
    name: str,
    description: str | None = None,
    status: str | None = None,
    organization_id: str = None,
    user_id: str = None,
    commit: bool = True,
) -> Behavior:
    """Get or create a behavior with optional description and status using optimized approach - no session variables needed."""
    # Prepare behavior data - only include non-None values
    behavior_data = {"name": name}

    # Add description only if provided
    if description is not None:
        behavior_data["description"] = description

    # Add status if provided
    if status:
        status_obj = get_or_create_status(
            db=db, name=status, entity_type=EntityType.GENERAL, 
            organization_id=organization_id, user_id=user_id, commit=commit
        )
        behavior_data["status_id"] = status_obj.id

    # Use get_or_create_entity for consistent lookup logic
    return get_or_create_entity(db, Behavior, behavior_data, organization_id, user_id, commit=commit)

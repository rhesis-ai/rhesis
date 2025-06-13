"""
Utility functions for CRUD operations
"""

import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from rhesis.backend.app.database import (
    get_current_organization_id,
    get_current_user_id,
    maintain_tenant_context,
)
from rhesis.backend.app.models import Behavior, Category, Status, Topic, TypeLookup
from rhesis.backend.app.utils.model_utils import QueryBuilder
from rhesis.backend.logging import logger
from rhesis.backend.app.constants import EntityType

# Define a generic type variable
T = TypeVar("T")


def get_item(db: Session, model: Type[T], item_id: uuid.UUID) -> Optional[T]:
    """Get a single item by ID"""
    with maintain_tenant_context(db):
        return (
            QueryBuilder(db, model)
            .with_organization_filter()
            .with_visibility_filter()
            .filter_by_id(item_id)
        )


def get_item_detail(db: Session, model: Type[T], item_id: uuid.UUID) -> Optional[T]:
    """Get a single item with all its relationships loaded"""
    with maintain_tenant_context(db):
        return (
            QueryBuilder(db, model)
            .with_joinedloads()
            .with_organization_filter()
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
) -> List[T]:
    """Get multiple items with pagination and sorting"""
    with maintain_tenant_context(db):
        return (
            QueryBuilder(db, model)
            .with_organization_filter()
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
) -> List[T]:
    """Get items with detail loading and proper filtering"""
    with maintain_tenant_context(db):
        return (
            QueryBuilder(db, model)
            .with_joinedloads()
            .with_organization_filter()
            .with_visibility_filter()
            .with_odata_filter(filter)
            .with_pagination(skip, limit)
            .with_sorting(sort_by, sort_order)
            .all()
        )


def create_item(db: Session, model: Type[T], item_data: Dict[str, Any] | BaseModel) -> T:
    """Create a new item"""
    # Convert Pydantic models to dict if needed
    if hasattr(item_data, "model_dump"):
        item_data = item_data.model_dump()
    elif hasattr(item_data, "dict"):  # For older Pydantic versions
        item_data = item_data.dict()

    # Clean up empty string values for UUID fields to prevent errors
    for field_name, field_value in list(item_data.items()):
        if field_value == "":
            # Check if this is a UUID/GUID field
            if hasattr(model, field_name):
                column = getattr(model, field_name)
                # Check column type more robustly
                if hasattr(column, 'type'):
                    field_type = str(column.type)
                    # Check for various UUID type representations
                    if (field_type.startswith("UUID") or 
                        field_type.startswith("GUID") or
                        "uuid" in field_type.lower() or
                        field_name.endswith("_id")):  # Also treat all _id fields as potential UUIDs
                        logger.debug(f"Converting empty string to None for UUID/GUID field {field_name}")
                        item_data[field_name] = None

    # Get model columns to check for organization_id and user_id
    columns = inspect(model).columns.keys()

    # Auto-populate organization_id if the model has this field and it's not already set
    if "organization_id" in columns and (not item_data.get("organization_id")):
        org_id = get_current_organization_id(db)
        if org_id:
            item_data["organization_id"] = org_id
            logger.debug(f"Auto-populated organization_id: {org_id}")

    # Auto-populate user_id if the model has this field and it's not already set
    if "user_id" in columns and (not item_data.get("user_id")):
        user_id = get_current_user_id(db)
        if user_id:
            item_data["user_id"] = user_id
            logger.debug(f"Auto-populated user_id: {user_id}")

    db_item = model(**item_data)
    logger.debug(f"Initiating database operation: {db_item}")
    with maintain_tenant_context(db):
        logger.debug(f"Adding item to database: {db_item}")
        db.add(db_item)
        logger.debug(f"Flushing database: {db_item}")
        db.flush()  # Flush to get the ID and other generated values
        logger.debug(f"Refreshing database: {db_item}")
        db.refresh(db_item)  # Refresh to ensure we have all generated values
        
        logger.debug(f"Committing database: {db_item}")
        db.commit()
        
        logger.debug(f"Returning database item: {db_item}")
        return db_item


def update_item(
    db: Session,
    model: Type[T],
    item_id: uuid.UUID,
    item_data: Dict[str, Any] | BaseModel,
) -> Optional[T]:
    """Update an existing item"""
    with maintain_tenant_context(db):
        db_item = get_item(db, model, item_id)
        if db_item is None:
            return None

        # Convert Pydantic models to dict if needed
        if hasattr(item_data, "model_dump"):
            item_data = item_data.model_dump(exclude_unset=True)
        elif hasattr(item_data, "dict"):  # For older Pydantic versions
            item_data = item_data.dict(exclude_unset=True)

        # Clean up empty string values for UUID fields to prevent errors
        for field_name, field_value in list(item_data.items()):
            if field_value == "":
                # Check if this is a UUID/GUID field
                if hasattr(model, field_name):
                    column = getattr(model, field_name)
                    # Check column type more robustly
                    if hasattr(column, 'type'):
                        field_type = str(column.type)
                        # Check for various UUID type representations
                        if (field_type.startswith("UUID") or 
                            field_type.startswith("GUID") or
                            "uuid" in field_type.lower() or
                            field_name.endswith("_id")):  # Also treat all _id fields as potential UUIDs
                            logger.debug(f"Converting empty string to None for UUID/GUID field {field_name}")
                            item_data[field_name] = None

        # Update item attributes
        for key, value in item_data.items():
            if hasattr(db_item, key):
                setattr(db_item, key, value)

        db.flush()  # Flush changes before commit
        db.refresh(db_item)  # Refresh to get updated values
        db.commit()
        
        return db_item


def delete_item(db: Session, model: Type[T], item_id: uuid.UUID) -> Optional[T]:
    """Delete an item and return the deleted item"""
    with maintain_tenant_context(db):
        db_item = get_item(db, model, item_id)
        if db_item is None:
            return None

        # Store a reference to the item before deletion
        deleted_item = db_item

        db.delete(db_item)
        db.commit()
        
        # Note: For deleted items, we can't refresh since they're deleted
        # The object should already have all its data loaded from the get_item call
        logger.debug(f"Deleted object returned: {deleted_item}")
        
        return deleted_item


def get_or_create_entity(db: Session, model: Type[T], entity_data: Dict[str, Any] | BaseModel) -> T:
    """
    Get or create an entity based on the provided entity data.
    Will attempt to find an existing entity using unique identifying fields 
    before creating a new one.
    The lookup will always include organization_id if the model supports it.
    """

    with maintain_tenant_context(db):
        # Convert Pydantic models to dict if needed
        if hasattr(entity_data, "model_dump"):
            search_data = entity_data.model_dump()
        elif hasattr(entity_data, "dict"):  # For older Pydantic versions
            search_data = entity_data.dict()
        else:
            search_data = entity_data

        # Build query with both session-based and explicit organization filtering
        query = QueryBuilder(db, model).with_organization_filter().with_visibility_filter()

        # Get model columns to identify searchable fields
        columns = inspect(model).columns.keys()
        search_filters = []

        # Always include organization_id in search if it's part of the model and data
        if "organization_id" in columns and "organization_id" in search_data:
            search_filters.append(
                getattr(model, "organization_id") == search_data["organization_id"]
            )

        # First try to find by ID if provided
        if "id" in search_data and search_data["id"]:
            db_entity = query.with_custom_filter(
                lambda q: q.filter(
                    model.id == search_data["id"],
                    *search_filters,  # Include organization_id filter
                )
            ).first()
            if db_entity:
                return db_entity

        # Add model-specific identifying fields
        if model.__name__ == "TypeLookup":
            # For TypeLookup, we need both type_name and type_value
            if "type_name" in search_data and "type_value" in search_data:
                search_filters.extend(
                    [
                        model.type_name == search_data["type_name"],
                        model.type_value == search_data["type_value"],
                    ]
                )
        elif hasattr(model, "content"):
            # For models using content as identifier
            if "content" in search_data:
                search_filters.append(model.content == search_data["content"])
        else:
            # For standard models using name, code, etc.
            identifying_fields = ["name", "code", "external_id", "slug", "nano_id"]
            for field in identifying_fields:
                if field in search_data and field in columns and search_data[field]:
                    search_filters.append(getattr(model, field) == search_data[field])

        # Only try to find existing entity if we have both organization and identifying filters
        if len(search_filters) > 1:  # At least organization_id and one identifying field
            db_entity = query.with_custom_filter(lambda q: q.filter(*search_filters)).first()
            if db_entity:
                return db_entity

        # If no existing entity found, create new one with all provided data
        return create_item(db, model, entity_data)


def get_or_create_status(db: Session, name: str, entity_type) -> Status:
    """Helper function to get or create a status"""
    # Handle EntityType enum or string
    entity_type_value = entity_type.value if hasattr(entity_type, 'value') else entity_type
    
    # First get or create the entity type lookup
    entity_type_lookup = get_or_create_type_lookup(
        db=db, type_name="EntityType", type_value=entity_type_value
    )

    # Try to find existing status using QueryBuilder
    query = (
        QueryBuilder(db, Status)
        .with_organization_filter()
        .with_visibility_filter()
        .with_custom_filter(
            lambda q: q.filter(Status.name == name, Status.entity_type_id == entity_type_lookup.id)
        )
    )

    existing_status = query.first()
    if existing_status:
        return existing_status

    # Create new status if not found
    return create_item(
        db=db, model=Status, item_data={"name": name, "entity_type_id": entity_type_lookup.id}
    )


def get_or_create_type_lookup(db: Session, type_name: str, type_value: str) -> TypeLookup:
    """Helper function to get or create a type lookup"""
    # Try to find existing type lookup using QueryBuilder
    query = (
        QueryBuilder(db, TypeLookup)
        .with_organization_filter()
        .with_visibility_filter()
        .with_custom_filter(
            lambda q: q.filter(
                TypeLookup.type_name == type_name, TypeLookup.type_value == type_value
            )
        )
    )

    existing_type = query.first()
    if existing_type:
        return existing_type

    # Create new type lookup if not found
    return create_item(
        db=db, model=TypeLookup, item_data={"type_name": type_name, "type_value": type_value}
    )


def get_or_create_topic(
    db: Session,
    name: str,
    entity_type: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> Topic:
    """Helper function to get or create a topic with optional entity type, description and status"""
    # Get entity type lookup if provided
    entity_type_id = None
    if entity_type:
        entity_type_lookup = get_or_create_type_lookup(
            db=db, type_name="EntityType", type_value=entity_type
        )
        entity_type_id = entity_type_lookup.id

    # Try to find existing topic using QueryBuilder
    query = (
        QueryBuilder(db, Topic)
        .with_organization_filter()
        .with_visibility_filter()
        .with_custom_filter(lambda q: q.filter(Topic.name == name))
    )

    # Add entity type to filter if provided
    if entity_type_id:
        query = query.with_custom_filter(lambda q: q.filter(Topic.entity_type_id == entity_type_id))

    existing_topic = query.first()
    if existing_topic:
        return existing_topic

    # Get status if provided
    status_id = None
    if status:
        status_obj = get_or_create_status(db=db, name=status, entity_type=EntityType.GENERAL)
        status_id = status_obj.id

    # Create new topic if not found
    return create_item(
        db=db,
        model=Topic,
        item_data={
            "name": name,
            "description": description,
            "entity_type_id": entity_type_id,
            "status_id": status_id,
        },
    )


def get_or_create_category(
    db: Session,
    name: str,
    entity_type: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> Category:
    """Helper function to get or create a category with optional entity type, description 
    and status"""
    # Get entity type lookup if provided
    entity_type_id = None
    if entity_type:
        entity_type_lookup = get_or_create_type_lookup(
            db=db, type_name="EntityType", type_value=entity_type
        )
        entity_type_id = entity_type_lookup.id

    # Try to find existing category using QueryBuilder
    query = (
        QueryBuilder(db, Category)
        .with_organization_filter()
        .with_visibility_filter()
        .with_custom_filter(lambda q: q.filter(Category.name == name))
    )

    # Add entity type to filter if provided
    if entity_type_id:
        query = query.with_custom_filter(
            lambda q: q.filter(Category.entity_type_id == entity_type_id)
        )

    existing_category = query.first()
    if existing_category:
        return existing_category

    # Get status if provided
    status_id = None
    if status:
        status_obj = get_or_create_status(db=db, name=status, entity_type=EntityType.GENERAL)
        status_id = status_obj.id

    # Create new category if not found
    return create_item(
        db=db,
        model=Category,
        item_data={
            "name": name,
            "description": description,
            "entity_type_id": entity_type_id,
            "status_id": status_id,
        },
    )


def count_items(
    db: Session,
    model: Type[T],
    filter: str = None,
) -> int:
    """Get the total count of items matching filters (without pagination)"""
    with maintain_tenant_context(db):
        return (
            QueryBuilder(db, model)
            .with_organization_filter()
            .with_visibility_filter()
            .with_odata_filter(filter)
            .count()
        )


def get_or_create_behavior(
    db: Session,
    name: str,
    description: str | None = None,
    status: str | None = None,
) -> Behavior:
    """Helper function to get or create a behavior with optional description and status"""
    # Try to find existing behavior using QueryBuilder
    query = (
        QueryBuilder(db, Behavior)
        .with_organization_filter()
        .with_visibility_filter()
        .with_custom_filter(lambda q: q.filter(Behavior.name == name))
    )

    existing_behavior = query.first()
    if existing_behavior:
        return existing_behavior

    # Get status if provided
    status_id = None
    if status:
        status_obj = get_or_create_status(db=db, name=status, entity_type=EntityType.GENERAL)
        status_id = status_obj.id

    # Create new behavior if not found
    return create_item(
        db=db,
        model=Behavior,
        item_data={"name": name, "description": description, "status_id": status_id},
    )

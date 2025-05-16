from typing import Any, Dict, List, Optional, Type

from pydantic import UUID4, BaseModel, create_model

from rhesis.backend.app.schemas.base import Base
from rhesis.backend.app.schemas.endpoint import Endpoint
from rhesis.backend.app.schemas.tag import TagRead
from rhesis.backend.app.schemas.test_set import TestSet
from rhesis.backend.app.utils.model_utils import get_model_relationships


def create_detailed_schema(
    base_schema: Type[Base], model: Type, schema_registry: Dict[str, Type[BaseModel]] = None
) -> Type[Base]:
    """
    Dynamically create a detailed schema with expanded relationships

    Args:
        base_schema: The base Pydantic schema
        model: The SQLAlchemy model
        schema_registry: Registry of already created schemas to avoid circular refs
    """
    if schema_registry is None:
        schema_registry = {}

    # Get model relationships using the utility function
    relationships = get_model_relationships(model)

    # Create fields dict for new schema
    fields: Dict[str, Any] = {}

    # Define common fields that should be included
    common_fields = [
        ("id", UUID4, ...),  # Always include ID
        ("nano_id", Optional[str], ...),  # Always include ID
        ("name", Optional[str], None),
        ("title", Optional[str], None),
        ("description", Optional[str], None),
        ("content", Optional[str], None),
        ("expected_response", Optional[str], None),
        ("type_name", Optional[str], None),
        ("type_value", Optional[str], None),
        ("email", Optional[str], None),
        ("family_name", Optional[str], None),
        ("given_name", Optional[str], None),
        ("picture", Optional[str], None),
        # Special case fields that should always be included
        ("test_set", Optional[TestSet], None),
        ("endpoint", Optional[Endpoint], None),
        ("user_id", Optional[UUID4], None),
        ("organization_id", Optional[UUID4], None),
        ("status_id", Optional[UUID4], None),
        ("attributes", Optional[Dict[str, Any]], None),
        ("tags", Optional[List[TagRead]], None),
        ("icon", Optional[str], None),
    ]

    # Apply common fields to top-level schema if they exist in the model
    for field_name, field_type, default_value in common_fields:
        if hasattr(model, field_name):
            fields[field_name] = (field_type, default_value)

    for rel_name, rel in relationships.items():
        # Get target model
        target_model = rel.mapper.class_

        # Check if we already have a schema for this model
        if target_model.__name__ in schema_registry:
            related_schema = schema_registry[target_model.__name__]
        else:
            # Create schema fields for related model
            schema_fields = {}

            # Only include fields that exist in the target model AND are in common_fields
            for field_name, field_type, default_value in common_fields:
                if hasattr(target_model, field_name):
                    schema_fields[field_name] = (field_type, default_value)

            # Create the schema
            related_schema = create_model(
                f"{target_model.__name__}Reference", **schema_fields, __base__=Base
            )

            # Store in registry to avoid circular references
            schema_registry[target_model.__name__] = related_schema

        # For scalar relationships (many-to-one, one-to-one), use Optional
        fields[rel_name] = (Optional[related_schema], None)

    # Create new schema class
    detailed_schema = create_model(f"{base_schema.__name__}Detail", __base__=base_schema, **fields)

    return detailed_schema

from typing import Any, Dict, List, Optional, Type, Set

from pydantic import UUID4, BaseModel, create_model

from rhesis.backend.app.schemas.base import Base
from rhesis.backend.app.schemas.endpoint import Endpoint
from rhesis.backend.app.schemas.tag import TagRead
from rhesis.backend.app.schemas.test_set import TestSet
from rhesis.backend.app.utils.model_utils import get_model_relationships


def create_detailed_schema(
    base_schema: Type[Base], 
    model: Type, 
    schema_registry: Dict[str, Type[BaseModel]] = None,
    include_nested_relationships: Optional[Dict[str, List[str]]] = None
) -> Type[Base]:
    """
    Dynamically create a detailed schema with expanded relationships

    Args:
        base_schema: The base Pydantic schema
        model: The SQLAlchemy model
        schema_registry: Registry of already created schemas to avoid circular refs
        include_nested_relationships: Dict mapping relationship names to list of nested relationships to include
                                     e.g., {"test_configuration": ["endpoint"]} for TestRun
    """
    if schema_registry is None:
        schema_registry = {}
    
    if include_nested_relationships is None:
        include_nested_relationships = {}

    # Get model relationships using the utility function
    relationships = get_model_relationships(model)
    relationship_names = set(relationships.keys())

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
        ("user_id", Optional[UUID4], None),
        ("organization_id", Optional[UUID4], None),
        ("status_id", Optional[UUID4], None),
        ("attributes", Optional[Dict[str, Any]], None),
        ("tags", Optional[List[TagRead]], None),
        ("icon", Optional[str], None),
        ("endpoint_id", Optional[UUID4], None),

    ]

    # Apply common fields to top-level schema if they exist in the model
    # BUT skip any fields that are also relationships - we'll handle those separately
    for field_name, field_type, default_value in common_fields:
        if hasattr(model, field_name) and field_name not in relationship_names:
            fields[field_name] = (field_type, default_value)

    # Handle relationship fields
    for rel_name, rel in relationships.items():
        # Get target model
        target_model = rel.mapper.class_

        # Special handling for known relationship types
        if rel_name == "endpoint":
            fields[rel_name] = (Optional[Endpoint], None)
            continue
            
        # Check if we already have a schema for this model
        schema_key = f"{target_model.__name__}Reference"
        if schema_key in schema_registry:
            related_schema = schema_registry[schema_key]
        else:
            # Create schema fields for related model
            schema_fields = {}

            # Only include fields that exist in the target model AND are in common_fields
            for field_name, field_type, default_value in common_fields:
                if hasattr(target_model, field_name):
                    schema_fields[field_name] = (field_type, default_value)

            # Handle nested relationships if specified
            if rel_name in include_nested_relationships:
                nested_relationships = get_model_relationships(target_model)
                for nested_rel_name in include_nested_relationships[rel_name]:
                    if nested_rel_name in nested_relationships:
                        nested_rel = nested_relationships[nested_rel_name]
                        nested_target_model = nested_rel.mapper.class_
                        
                        # Special handling for known nested relationship types
                        if nested_rel_name == "endpoint":
                            schema_fields[nested_rel_name] = (Optional[Endpoint], None)
                        else:
                            # Create a simple reference schema for the nested relationship
                            nested_schema_fields = {}
                            for field_name, field_type, default_value in common_fields:
                                if hasattr(nested_target_model, field_name):
                                    nested_schema_fields[field_name] = (field_type, default_value)
                            
                            nested_schema_key = f"{nested_target_model.__name__}Reference"
                            if nested_schema_key not in schema_registry:
                                nested_schema = create_model(
                                    nested_schema_key, **nested_schema_fields, __base__=Base
                                )
                                schema_registry[nested_schema_key] = nested_schema
                            else:
                                nested_schema = schema_registry[nested_schema_key]
                            
                            schema_fields[nested_rel_name] = (Optional[nested_schema], None)

            # Create the schema
            related_schema = create_model(
                schema_key, **schema_fields, __base__=Base
            )

            # Store in registry to avoid circular references
            schema_registry[schema_key] = related_schema

        # For scalar relationships (many-to-one, one-to-one), use Optional
        fields[rel_name] = (Optional[related_schema], None)

    # Create new schema class
    detailed_schema = create_model(f"{base_schema.__name__}Detail", __base__=base_schema, **fields)

    return detailed_schema

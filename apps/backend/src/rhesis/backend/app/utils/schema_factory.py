from typing import Any, Dict, List, Optional, Type, Set, Union

from pydantic import UUID4, BaseModel, create_model

from rhesis.backend.app.schemas.base import Base
from rhesis.backend.app.schemas.tag import TagRead
from rhesis.backend.app.schemas.test_set import TestSet
from rhesis.backend.app.utils.model_utils import get_model_relationships


def create_detailed_schema(
    base_schema: Type[Base], 
    model: Type, 
    schema_registry: Dict[str, Type[BaseModel]] = None,
    include_nested_relationships: Optional[Dict[str, Union[List[str], Dict[str, Any]]]] = None
) -> Type[Base]:
    """
    Dynamically create a detailed schema with expanded relationships

    Args:
        base_schema: The base Pydantic schema
        model: The SQLAlchemy model
        schema_registry: Registry of already created schemas to avoid circular refs
        include_nested_relationships: Dict mapping relationship names to nested relationships to include
                                     Can be:
                                     - List[str]: Simple list of relationship names for second-order
                                     - Dict[str, Any]: Nested dictionary for deeper relationships
                                     
                                     Examples:
                                     - {"test_configuration": ["endpoint"]} for second-order
                                     - {"test_configuration": {"endpoint": ["project"]}} for third-order
                                     - {"test_configuration": {"endpoint": {"project": ["status"]}}} for fourth-order
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
        # Model-specific fields
        ("model_name", Optional[str], None),
        ("endpoint", Optional[str], None),  # Regular field for Model, relationship for others
        # Special case fields that should always be included
        ("test_set", Optional[TestSet], None),
        ("user_id", Optional[UUID4], None),
        ("organization_id", Optional[UUID4], None),
        ("status_id", Optional[UUID4], None),
        ("attributes", Optional[Dict[str, Any]], None),
        ("tags", Optional[List[TagRead]], None),
        ("icon", Optional[str], None),
        ("endpoint_id", Optional[UUID4], None),
        ("project_id", Optional[UUID4], None),

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
                nested_spec = include_nested_relationships[rel_name]
                
                if isinstance(nested_spec, list):
                    # Simple list format: ["endpoint", "project"]
                    _handle_nested_relationships_simple(
                        target_model, nested_spec, schema_fields, schema_registry, common_fields
                    )
                elif isinstance(nested_spec, dict):
                    # Nested dict format: {"endpoint": ["project"]} or {"endpoint": {"project": ["status"]}}
                    _handle_nested_relationships_deep(
                        target_model, nested_spec, schema_fields, schema_registry, common_fields
                    )

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


def _handle_nested_relationships_simple(
    target_model: Type,
    nested_relationship_names: List[str],
    schema_fields: Dict[str, Any],
    schema_registry: Dict[str, Type[BaseModel]],
    common_fields: List[tuple]
):
    """Handle simple nested relationships (second-order only)"""
    nested_relationships = get_model_relationships(target_model)
    
    for nested_rel_name in nested_relationship_names:
        if nested_rel_name in nested_relationships:
            nested_rel = nested_relationships[nested_rel_name]
            nested_target_model = nested_rel.mapper.class_
            
            # Create a reference schema for the nested relationship
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


def _handle_nested_relationships_deep(
    target_model: Type,
    nested_spec: Dict[str, Any],
    schema_fields: Dict[str, Any],
    schema_registry: Dict[str, Type[BaseModel]],
    common_fields: List[tuple]
):
    """Handle deep nested relationships (third-order and beyond)"""
    nested_relationships = get_model_relationships(target_model)
    
    for nested_rel_name, deeper_spec in nested_spec.items():
        if nested_rel_name in nested_relationships:
            nested_rel = nested_relationships[nested_rel_name]
            nested_target_model = nested_rel.mapper.class_
            
            # Create schema fields for the nested relationship
            nested_schema_fields = {}
            for field_name, field_type, default_value in common_fields:
                if hasattr(nested_target_model, field_name):
                    nested_schema_fields[field_name] = (field_type, default_value)
            
            # Recursively handle deeper relationships
            if isinstance(deeper_spec, list):
                # deeper_spec is a list like ["project", "status"]
                _handle_nested_relationships_simple(
                    nested_target_model, deeper_spec, nested_schema_fields, schema_registry, common_fields
                )
            elif isinstance(deeper_spec, dict):
                # deeper_spec is a dict like {"project": ["status"]} or {"project": {"status": ["..."]}}
                _handle_nested_relationships_deep(
                    nested_target_model, deeper_spec, nested_schema_fields, schema_registry, common_fields
                )
            
            # Create schema for this nested relationship
            nested_schema_key = f"{nested_target_model.__name__}Reference"
            if nested_schema_key not in schema_registry:
                nested_schema = create_model(
                    nested_schema_key, **nested_schema_fields, __base__=Base
                )
                schema_registry[nested_schema_key] = nested_schema
            else:
                nested_schema = schema_registry[nested_schema_key]
            
            schema_fields[nested_rel_name] = (Optional[nested_schema], None)

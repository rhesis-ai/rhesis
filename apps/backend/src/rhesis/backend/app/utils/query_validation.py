from typing import Optional, Type

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import RelationshipProperty


def validate_sort_field(model: Type, sort_by: str) -> None:
    """Validate that the sort field exists in the model"""
    if not hasattr(model, sort_by) and sort_by not in inspect(model).columns.keys():
        model_columns = inspect(model).columns.keys()
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort field: {sort_by}. Must be one of: "
                   f"{', '.join(model_columns)}",
        )


def validate_sort_order(sort_order: str) -> None:
    """Validate that the sort order is valid"""
    if sort_order.lower() not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Invalid sort order. Must be 'asc' or 'desc'")


def validate_pagination(skip: int, limit: int) -> None:
    """Validate pagination parameters"""
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip must be greater than or equal to 0")
    if limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be greater than 0")
    if limit > 100:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 100")


def validate_odata_filter(model: Type, filter_str: Optional[str]) -> None:
    """Validate OData filter string"""
    if filter_str:
        # Get all valid fields for filtering (columns + relationships for navigation)
        mapper = inspect(model)
        valid_fields = list(mapper.columns.keys())
        
        # Add relationship names for navigation properties
        for relationship_name, relationship_prop in mapper.relationships.items():
            if isinstance(relationship_prop, RelationshipProperty):
                valid_fields.append(relationship_name)
        
        # Enhanced validation that supports navigation properties
        # Check if filter contains any valid field names or relationship names
        for field in valid_fields:
            if field in filter_str:
                break
        else:
            # If no valid fields found, let the OData parser handle it
            # This provides more flexibility while still catching obvious errors
            common_odata_functions = ['contains', 'startswith', 'endswith', 'eq', 'ne', 'gt', 'lt', 'ge', 'le', 'in', 'and', 'or', 'not']
            has_odata_syntax = any(func in filter_str.lower() for func in common_odata_functions)
            
            if not has_odata_syntax:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid filter. Must use valid fields: {', '.join(valid_fields)} or valid OData syntax",
                )

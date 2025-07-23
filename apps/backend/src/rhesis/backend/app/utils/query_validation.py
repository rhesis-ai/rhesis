from typing import Optional, Type

from fastapi import HTTPException
from sqlalchemy import inspect


def validate_pagination(skip: int, limit: int) -> None:
    """Validate pagination parameters"""
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip cannot be negative")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be positive")
    if limit > 100:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 100")


def validate_sort_field(model: Type, sort_field: str) -> None:
    """Validate sort field exists on model"""
    if not hasattr(model, sort_field):
        valid_fields = inspect(model).columns.keys()
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort field '{sort_field}'. Must use valid fields: {', '.join(valid_fields)}"
        )


def validate_sort_order(sort_order: str) -> None:
    """Validate sort order is valid"""
    if sort_order.lower() not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Sort order must be 'asc' or 'desc'")


def validate_odata_filter(model: Type, filter_str: Optional[str]) -> None:
    """Validate OData filter string"""
    if filter_str:
        # Get all valid direct column fields
        valid_fields = set(inspect(model).columns.keys())
        
        # Get all valid relationship fields
        mapper = inspect(model)
        for rel in mapper.relationships:
            valid_fields.add(rel.key)
        
        # Check if the filter contains any valid field names
        # This is a basic validation - the actual OData parser will do more thorough validation
        filter_lower = filter_str.lower()
        
        # Check for direct fields or relationship navigation (with / or .)
        found_valid_field = False
        for field in valid_fields:
            if field.lower() in filter_lower:
                found_valid_field = True
                break
        
        # Also check for common relationship navigation patterns
        # like "behavior/name", "topic/name", etc.
        relationship_patterns = [
            'behavior/', 'topic/', 'category/', 'assignee/', 'owner/', 
            'user/', 'status/', 'prompt/', 'organization/'
        ]
        
        for pattern in relationship_patterns:
            if pattern in filter_lower:
                found_valid_field = True
                break
        
        if not found_valid_field:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter. Must reference valid fields or relationships. Available fields: {', '.join(sorted(valid_fields))}"
            )

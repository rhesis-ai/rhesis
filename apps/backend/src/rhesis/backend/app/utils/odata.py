from typing import Type

from fastapi import HTTPException
from odata_query.sqlalchemy import apply_odata_query
from sqlalchemy.orm import Query


def apply_odata_filter(query: Query, model: Type, filter_expr: str | None) -> Query:
    """Apply OData filter to query if provided"""
    if filter_expr:
        try:
            return apply_odata_query(query, filter_expr)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing filter: {str(e)}")
    return query


def combine_entity_type_filter(base_filter: str | None, entity_type: str | None) -> str | None:
    """
    Combines a base OData filter with an entity type filter.

    Args:
        base_filter: The existing OData filter expression, if any
        entity_type: The entity type value to filter by

    Returns:
        Combined OData filter expression or None if no filters
    """
    if not entity_type:
        return base_filter

    # Create entity type filter using OData navigation syntax
    # The Status model has an entity_type relationship to TypeLookup
    # We need to match both type_name='EntityType' and type_value=entity_type
    entity_type_filter = (
        f"entity_type/type_name eq 'EntityType' and entity_type/type_value eq '{entity_type}'"
    )

    # Combine with existing filter if present
    if base_filter:
        return f"({base_filter}) and ({entity_type_filter})"

    return entity_type_filter

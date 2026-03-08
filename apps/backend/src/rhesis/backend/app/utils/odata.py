from typing import Any, Dict, List, Type, Union

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


def apply_select(
    data: Union[List[Dict[str, Any]], Dict[str, Any], Any],
    select: str | None,
) -> Union[List[Dict[str, Any]], Dict[str, Any], Any]:
    """Filter serialized response data to include only selected fields.

    Accepts a comma-separated list of field names (OData ``$select``).
    ``id`` is always included so that entities remain identifiable.

    Works on both single dicts and lists of dicts.  If *data* is a list
    of ORM/Pydantic objects, each item is converted via ``model_dump()``
    (Pydantic v2) or ``dict()`` first.
    """
    if not select:
        return data

    fields = {f.strip() for f in select.split(",") if f.strip()}
    fields.add("id")  # always include id

    def _pick(obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict):
            d = obj
        elif hasattr(obj, "model_dump"):
            d = obj.model_dump()
        elif hasattr(obj, "dict"):
            d = obj.dict()
        else:
            d = obj.__dict__
        return {k: v for k, v in d.items() if k in fields}

    if isinstance(data, list):
        return [_pick(item) for item in data]
    return _pick(data)


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

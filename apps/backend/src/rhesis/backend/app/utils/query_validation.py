from typing import Optional, Type

from fastapi import HTTPException
from sqlalchemy import inspect


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
        # Get all valid fields for filtering
        valid_fields = inspect(model).columns.keys()
        # Basic validation that the filter string contains valid field names
        # This is a simple check - the actual OData parser will do more thorough validation
        for field in valid_fields:
            if field in filter_str:
                break
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter. Must use valid fields: {', '.join(valid_fields)}",
            )

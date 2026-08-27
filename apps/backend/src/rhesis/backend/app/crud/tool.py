"""CRUD operations for tools."""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

_TOOL_RELATED_FIELDS = (include(models.Tool.tool_provider_type),)


def get_tool(
    db: Session, tool_id: uuid.UUID, organization_id: str, user_id: str = None
) -> Optional[models.Tool]:
    """Get a specific tool by ID with relationships loaded"""
    return get_item_detail(
        db,
        models.Tool,
        tool_id,
        organization_id=organization_id,
        user_id=user_id,
        related_fields=_TOOL_RELATED_FIELDS,
    )


def get_tools(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Tool]:
    """Get all tools for an organization with filtering and pagination"""
    return (
        QueryBuilder(db, models.Tool)
        .with_related(*_TOOL_RELATED_FIELDS)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_tool(
    db: Session, tool: schemas.ToolCreate, organization_id: str, user_id: str = None
) -> models.Tool:
    """Create a new tool"""
    return create_item(db, models.Tool, tool, organization_id, user_id)


def update_tool(
    db: Session,
    tool_id: uuid.UUID,
    tool: schemas.ToolUpdate,
    organization_id: str,
    user_id: str = None,
) -> Optional[models.Tool]:
    """Update a tool"""
    return update_item(db, models.Tool, tool_id, tool, organization_id, user_id)


def delete_tool(
    db: Session, tool_id: uuid.UUID, organization_id: str, user_id: str = None
) -> Optional[models.Tool]:
    """Delete a tool (soft delete)"""
    return delete_item(db, models.Tool, tool_id, organization_id=organization_id, user_id=user_id)

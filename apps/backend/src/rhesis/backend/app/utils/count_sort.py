"""Virtual sort fields for entity activity counts (comments, tasks, tags)."""

from __future__ import annotations

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Query

from rhesis.backend.app.models.comment import Comment
from rhesis.backend.app.models.tag import TaggedItem
from rhesis.backend.app.models.task import Task

VIRTUAL_COUNT_SORT_FIELDS = frozenset({"comments_count", "tasks_count", "tags_count"})


def is_virtual_count_sort(sort_by: str | None) -> bool:
    return sort_by in VIRTUAL_COUNT_SORT_FIELDS


def model_supports_count_sort(model, sort_by: str) -> bool:
    if sort_by == "comments_count":
        return hasattr(model, "comments")
    if sort_by == "tasks_count":
        return hasattr(model, "tasks")
    if sort_by == "tags_count":
        return hasattr(model, "_tags_relationship") or hasattr(model, "tags")
    return False


def _count_subquery(model, related_model, entity_type: str):
    conditions = [
        related_model.entity_id == model.id,
        related_model.entity_type == entity_type,
    ]
    if hasattr(related_model, "deleted_at"):
        conditions.append(related_model.deleted_at.is_(None))

    return (
        select(func.count())
        .select_from(related_model)
        .where(and_(*conditions))
        .correlate(model)
        .scalar_subquery()
    )


def _tag_count_subquery(model, entity_type: str):
    return (
        select(func.count())
        .select_from(TaggedItem)
        .where(
            and_(
                TaggedItem.entity_id == model.id,
                TaggedItem.entity_type == entity_type,
            )
        )
        .correlate(model)
        .scalar_subquery()
    )


def apply_virtual_count_sort(query: Query, model, sort_by: str, sort_order: str) -> Query:
    """Order *query* by a correlated count subquery."""
    entity_type = model.__name__

    if sort_by == "comments_count":
        count_expr = _count_subquery(model, Comment, entity_type)
    elif sort_by == "tasks_count":
        count_expr = _count_subquery(model, Task, entity_type)
    elif sort_by == "tags_count":
        count_expr = _tag_count_subquery(model, entity_type)
    else:
        return query

    if sort_order == "desc":
        return query.order_by(desc(count_expr))
    return query.order_by(count_expr)

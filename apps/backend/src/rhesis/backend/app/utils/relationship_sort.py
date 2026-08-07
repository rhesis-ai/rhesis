"""Virtual sort fields backed by related model columns."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Query

from rhesis.backend.app.models.behavior import Behavior
from rhesis.backend.app.models.category import Category
from rhesis.backend.app.models.topic import Topic
from rhesis.backend.app.models.type_lookup import TypeLookup

_RELATIONSHIP_SORT_FIELDS = {
    "behavior.name": (Behavior, "name", "behavior_id"),
    "topic.name": (Topic, "name", "topic_id"),
    "category.name": (Category, "name", "category_id"),
    "test_type.type_value": (TypeLookup, "type_value", "test_type_id"),
}
VIRTUAL_RELATIONSHIP_SORT_FIELDS = frozenset(_RELATIONSHIP_SORT_FIELDS)


def is_virtual_relationship_sort(sort_by: str | None) -> bool:
    return sort_by in VIRTUAL_RELATIONSHIP_SORT_FIELDS


def model_supports_relationship_sort(model, sort_by: str) -> bool:
    relationship_sort = _RELATIONSHIP_SORT_FIELDS.get(sort_by)
    return relationship_sort is not None and hasattr(model, relationship_sort[2])


def _relationship_subquery(model, sort_by: str):
    related_model, related_column, foreign_key = _RELATIONSHIP_SORT_FIELDS[sort_by]
    return (
        select(getattr(related_model, related_column))
        .where(related_model.id == getattr(model, foreign_key))
        .correlate(model)
        .scalar_subquery()
    )


def apply_virtual_relationship_sort(
    query: Query,
    model,
    sort_by: str,
    sort_order: str,
) -> Query:
    """Order by a related column, or return the query unchanged if unsupported."""
    if not model_supports_relationship_sort(model, sort_by):
        return query

    sort_expression = _relationship_subquery(model, sort_by)
    if sort_order == "desc":
        return query.order_by(desc(sort_expression))
    return query.order_by(sort_expression)

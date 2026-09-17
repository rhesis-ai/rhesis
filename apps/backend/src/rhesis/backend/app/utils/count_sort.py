"""Virtual sort fields for entity activity counts (comments, tasks, tags, annotations)."""

from __future__ import annotations

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Query

from rhesis.backend.app.models.comment import Comment
from rhesis.backend.app.models.tag import TaggedItem
from rhesis.backend.app.models.task import Task

ANNOTATED_TESTS_SORT_FIELD = "annotated_tests_count"

VIRTUAL_COUNT_SORT_FIELDS = frozenset(
    {"comments_count", "tasks_count", "tags_count", ANNOTATED_TESTS_SORT_FIELD}
)


def is_virtual_count_sort(sort_by: str | None) -> bool:
    return sort_by in VIRTUAL_COUNT_SORT_FIELDS


def model_supports_count_sort(model, sort_by: str) -> bool:
    if sort_by == "comments_count":
        return hasattr(model, "comments")
    if sort_by == "tasks_count":
        return hasattr(model, "tasks")
    if sort_by == "tags_count":
        return hasattr(model, "_tags_relationship") or hasattr(model, "tags")
    if sort_by == ANNOTATED_TESTS_SORT_FIELD:
        return _owns_test_results(model)
    return False


def _owns_test_results(model) -> bool:
    """Only the entity test results are stamped against can be ordered by them.

    Asked of the foreign key rather than of an ``annotations`` attribute, which a run
    does not have -- its annotations hang off its test results -- and which SQLAlchemy
    would not attach until mappers are configured anyway. Validation can run before
    that, which would reject every such sort as unsupported.
    """
    from rhesis.backend.app.models.test_result import TestResult

    table = getattr(model, "__tablename__", None)
    return any(
        fk.column.table.name == table for fk in TestResult.__table__.c.test_run_id.foreign_keys
    )


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
                TaggedItem.deleted_at.is_(None),
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
    elif sort_by == ANNOTATED_TESTS_SORT_FIELD:
        if not _owns_test_results(model):
            return query
        # Imported here, not at module scope: query_validation imports this module at
        # import time, and app.crud pulls the model layer back through a half-built
        # query_utils. It lives there so the sort and the grid column that displays
        # the number are the same expression.
        from rhesis.backend.app.crud.annotation import annotated_tests_count_expr

        count_expr = annotated_tests_count_expr(model.id)
    else:
        return query

    if sort_order == "desc":
        return query.order_by(desc(count_expr))
    return query.order_by(count_expr)

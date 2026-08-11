"""Filters that keep metric-owned rows out of the user-facing lists.

A metric's tuning test set and its test cases live in the normal ``test_set`` /
``test`` tables but belong to a metric rather than to the user's own library.
Both the list query and the ``X-Total-Count`` header beside it have to exclude
them, or a grid shows a total that does not match the rows it can page through.

Used by ``crud/`` list functions and by the ``with_count_header`` decorator, so
it lives here rather than in either one.
"""

from typing import Callable, Type

from sqlalchemy.orm import Query


def exclude_metric_owned(model: Type) -> Callable[[Query], Query]:
    """Filter out rows owned by a metric (``metric_id IS NOT NULL``).

    ``model`` must have a ``metric_id`` column -- ``models.Test`` or
    ``models.TestSet``.
    """

    def _filter(query: Query) -> Query:
        return query.filter(model.metric_id.is_(None))

    return _filter

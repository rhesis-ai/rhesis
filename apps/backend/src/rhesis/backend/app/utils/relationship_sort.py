"""Virtual sort fields backed by related model columns.

Each entry in ``_RELATIONSHIP_SORT_FIELDS`` is either:

* A **single-hop** 3-tuple ``(RelatedModel, column, fk_on_root)`` for a
  direct FK on the queried model, or
* A **multi-hop** list of ``(Model, fk_column)`` pairs ending with a
  ``(Model, sort_column)`` pair, walking through intermediate tables.

Both forms produce a correlated scalar subquery so the sort works inside
the id-only phase-1 query without eager-loading the relationship.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Query

from rhesis.backend.app.models.category import Category
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.prompt import Prompt
from rhesis.backend.app.models.requirement import Requirement
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.models.topic import Topic
from rhesis.backend.app.models.type_lookup import TypeLookup

_RELATIONSHIP_SORT_FIELDS: dict[str, tuple | list] = {
    "requirement.name": (Requirement, "name", "requirement_id"),
    "topic.name": (Topic, "name", "topic_id"),
    "category.name": (Category, "name", "category_id"),
    "test_type.type_value": (TypeLookup, "type_value", "test_type_id"),
    "prompt.content": (Prompt, "content", "prompt_id"),
    "endpoint.name": [
        (TestConfiguration, "test_configuration_id"),
        (Endpoint, "endpoint_id"),
        "name",
    ],
    "test_set.name": [
        (TestConfiguration, "test_configuration_id"),
        (TestSet, "test_set_id"),
        "name",
    ],
}
VIRTUAL_RELATIONSHIP_SORT_FIELDS = frozenset(_RELATIONSHIP_SORT_FIELDS)


def is_virtual_relationship_sort(sort_by: str | None) -> bool:
    return sort_by in VIRTUAL_RELATIONSHIP_SORT_FIELDS


def _is_chain(entry: tuple | list) -> bool:
    return isinstance(entry, list)


def model_supports_relationship_sort(model, sort_by: str) -> bool:
    entry = _RELATIONSHIP_SORT_FIELDS.get(sort_by)
    if entry is None:
        return False
    if _is_chain(entry):
        return hasattr(model, entry[0][1])
    return hasattr(model, entry[2])


def _single_hop_subquery(model, sort_by: str):
    related_model, related_column, foreign_key = _RELATIONSHIP_SORT_FIELDS[sort_by]
    return (
        select(getattr(related_model, related_column))
        .where(related_model.id == getattr(model, foreign_key))
        .correlate(model)
        .scalar_subquery()
    )


def _chain_subquery(model, chain: list):
    """Build a correlated subquery walking a multi-hop chain.

    ``chain`` is ``[(IntermediateModel, fk_on_parent), ..., sort_column]``
    where the first ``fk_on_parent`` lives on ``model``.
    """
    sort_column = chain[-1]
    hops = chain[:-1]

    target_model = hops[-1][0]
    stmt = select(getattr(target_model, sort_column))

    prev_model = model
    for hop_model, fk_attr in hops:
        stmt = stmt.where(hop_model.id == getattr(prev_model, fk_attr))
        prev_model = hop_model

    return stmt.correlate(model).scalar_subquery()


def apply_virtual_relationship_sort(
    query: Query,
    model,
    sort_by: str,
    sort_order: str,
) -> Query:
    """Order by a related column, or return the query unchanged if unsupported."""
    if not model_supports_relationship_sort(model, sort_by):
        return query

    entry = _RELATIONSHIP_SORT_FIELDS[sort_by]
    if _is_chain(entry):
        sort_expression = _chain_subquery(model, entry)
    else:
        sort_expression = _single_hop_subquery(model, sort_by)

    if sort_order == "desc":
        return query.order_by(desc(sort_expression))
    return query.order_by(sort_expression)

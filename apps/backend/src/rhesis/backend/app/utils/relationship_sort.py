"""Virtual sort fields backed by related model columns."""

from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Query, aliased

from rhesis.backend.app.models.category import Category
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.prompt import Prompt
from rhesis.backend.app.models.requirement import Requirement
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.models.topic import Topic
from rhesis.backend.app.models.type_lookup import TypeLookup

# sort field -> (hops, column). Each hop is (model, fk on the previous model);
# the first fk lives on the model being sorted, the column on the last hop's model.
_RELATIONSHIP_SORT_FIELDS = {
    "requirement.name": (((Requirement, "requirement_id"),), "name"),
    "topic.name": (((Topic, "topic_id"),), "name"),
    "category.name": (((Category, "category_id"),), "name"),
    "test_type.type_value": (((TypeLookup, "test_type_id"),), "type_value"),
    "prompt.content": (((Prompt, "prompt_id"),), "content"),
    "endpoint.name": (
        ((TestConfiguration, "test_configuration_id"), (Endpoint, "endpoint_id")),
        "name",
    ),
    "test_set.name": (
        ((TestConfiguration, "test_configuration_id"), (TestSet, "test_set_id")),
        "name",
    ),
}
VIRTUAL_RELATIONSHIP_SORT_FIELDS = frozenset(_RELATIONSHIP_SORT_FIELDS)


def is_virtual_relationship_sort(sort_by: str | None) -> bool:
    return sort_by in VIRTUAL_RELATIONSHIP_SORT_FIELDS


def model_supports_relationship_sort(model, sort_by: str) -> bool:
    relationship_sort = _RELATIONSHIP_SORT_FIELDS.get(sort_by)
    if relationship_sort is None:
        return False
    hops, _column = relationship_sort
    return hasattr(model, hops[0][1])


def apply_virtual_relationship_sort(
    query: Query,
    model,
    sort_by: str,
    sort_order: str,
) -> Query:
    """Order by a related column, or return the query unchanged if unsupported.

    LEFT JOINs, not a correlated subquery: Postgres runs a subquery in ORDER BY
    once per matching row before LIMIT (~65x slower at 200k runs). Every hop is
    many-to-one on a primary key, so the joins add no rows; aliases keep them
    apart from joins the filters or eager loads add.
    """
    if not model_supports_relationship_sort(model, sort_by):
        return query

    hops, column = _RELATIONSHIP_SORT_FIELDS[sort_by]
    parent = model
    for related_model, foreign_key in hops:
        hop = aliased(related_model)
        query = query.outerjoin(hop, hop.id == getattr(parent, foreign_key))
        parent = hop

    sort_expression = getattr(parent, column)
    if sort_order == "desc":
        return query.order_by(desc(sort_expression))
    return query.order_by(sort_expression)

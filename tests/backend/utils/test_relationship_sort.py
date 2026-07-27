import pytest
from fastapi import HTTPException

from rhesis.backend.app.models.behavior import Behavior
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.query_utils import QueryBuilder
from rhesis.backend.app.utils.query_validation import validate_sort_field
from rhesis.backend.app.utils.relationship_sort import (
    apply_virtual_relationship_sort,
    is_virtual_relationship_sort,
    model_supports_relationship_sort,
)


@pytest.mark.parametrize(
    "sort_by",
    [
        "behavior.name",
        "topic.name",
        "category.name",
        "test_type.type_value",
    ],
)
def test_virtual_relationship_sort_detection(sort_by):
    assert is_virtual_relationship_sort(sort_by)
    assert not is_virtual_relationship_sort("behavior_id")


@pytest.mark.parametrize(
    "sort_by",
    [
        "behavior.name",
        "topic.name",
        "category.name",
        "test_type.type_value",
    ],
)
def test_model_supports_relationship_sort_for_test(sort_by):
    assert model_supports_relationship_sort(Test, sort_by)
    assert not model_supports_relationship_sort(Behavior, sort_by)


@pytest.mark.parametrize(
    "sort_by",
    [
        "behavior.name",
        "topic.name",
        "category.name",
        "test_type.type_value",
    ],
)
def test_validate_sort_field_accepts_relationship_sort_for_test(sort_by):
    validate_sort_field(Test, sort_by)


@pytest.mark.parametrize(
    "sort_by",
    [
        "behavior.name",
        "topic.name",
        "category.name",
        "test_type.type_value",
    ],
)
def test_validate_sort_field_rejects_relationship_sort_for_other_models(sort_by):
    with pytest.raises(HTTPException) as exc_info:
        validate_sort_field(Behavior, sort_by)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("sort_by", "related_column", "foreign_key"),
    [
        ("behavior.name", "behavior.name", "test.behavior_id"),
        ("topic.name", "topic.name", "test.topic_id"),
        ("category.name", "category.name", "test.category_id"),
        (
            "test_type.type_value",
            "type_lookup.type_value",
            "test.test_type_id",
        ),
    ],
)
@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_apply_relationship_sort_builds_correlated_subquery(
    test_db, sort_by, related_column, foreign_key, sort_order
):
    query = test_db.query(Test)
    sorted_query = apply_virtual_relationship_sort(query, Test, sort_by, sort_order)

    compiled = str(sorted_query.statement.compile(compile_kwargs={"literal_binds": True})).lower()
    related_table = related_column.split(".", maxsplit=1)[0]
    assert f"select {related_column}" in compiled
    assert f"{related_table}.id = {foreign_key}" in compiled
    assert "order by" in compiled
    if sort_order == "desc":
        assert " desc" in compiled


@pytest.mark.parametrize(
    ("sort_by", "related_column", "foreign_key"),
    [
        ("behavior.name", "behavior.name", "test.behavior_id"),
        ("topic.name", "topic.name", "test.topic_id"),
        ("category.name", "category.name", "test.category_id"),
        (
            "test_type.type_value",
            "type_lookup.type_value",
            "test.test_type_id",
        ),
    ],
)
def test_query_builder_dispatches_relationship_sort(test_db, sort_by, related_column, foreign_key):
    query = QueryBuilder(test_db, Test).with_sorting(sort_by, "asc").build()

    compiled = str(query.statement.compile(compile_kwargs={"literal_binds": True})).lower()
    related_table = related_column.split(".", maxsplit=1)[0]
    assert f"select {related_column}" in compiled
    assert f"{related_table}.id = {foreign_key}" in compiled


def test_apply_relationship_sort_keeps_query_unchanged_when_unsupported(test_db):
    query = test_db.query(Behavior)

    assert apply_virtual_relationship_sort(query, Behavior, "topic.name", "asc") is query

import pytest
from fastapi import HTTPException

from rhesis.backend.app.models.requirement import Requirement
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.utils.query_utils import QueryBuilder, include
from rhesis.backend.app.utils.query_validation import validate_sort_field
from rhesis.backend.app.utils.relationship_sort import (
    apply_virtual_relationship_sort,
    is_virtual_relationship_sort,
    model_supports_relationship_sort,
)


@pytest.mark.parametrize(
    "sort_by",
    [
        "requirement.name",
        "topic.name",
        "category.name",
        "test_type.type_value",
        "prompt.content",
    ],
)
def test_virtual_relationship_sort_detection(sort_by):
    assert is_virtual_relationship_sort(sort_by)
    assert not is_virtual_relationship_sort("requirement_id")


@pytest.mark.parametrize(
    "sort_by",
    [
        "requirement.name",
        "topic.name",
        "category.name",
        "test_type.type_value",
        "prompt.content",
    ],
)
def test_model_supports_relationship_sort_for_test(sort_by):
    assert model_supports_relationship_sort(Test, sort_by)
    assert not model_supports_relationship_sort(Requirement, sort_by)


@pytest.mark.parametrize(
    "sort_by",
    [
        "requirement.name",
        "topic.name",
        "category.name",
        "test_type.type_value",
        "prompt.content",
    ],
)
def test_validate_sort_field_accepts_relationship_sort_for_test(sort_by):
    validate_sort_field(Test, sort_by)


@pytest.mark.parametrize(
    "sort_by",
    [
        "requirement.name",
        "topic.name",
        "category.name",
        "test_type.type_value",
        "prompt.content",
    ],
)
def test_validate_sort_field_rejects_relationship_sort_for_other_models(sort_by):
    with pytest.raises(HTTPException) as exc_info:
        validate_sort_field(Requirement, sort_by)
    assert exc_info.value.status_code == 400


SINGLE_HOP_SORTS = [
    ("requirement.name", "requirement", "name", "requirement_id"),
    ("topic.name", "topic", "name", "topic_id"),
    ("category.name", "category", "name", "category_id"),
    ("test_type.type_value", "type_lookup", "type_value", "test_type_id"),
    ("prompt.content", "prompt", "content", "prompt_id"),
]


@pytest.mark.parametrize(("sort_by", "table", "column", "foreign_key"), SINGLE_HOP_SORTS)
@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_relationship_sort_left_joins_and_orders_by_alias(
    test_db, sort_by, table, column, foreign_key, sort_order
):
    query = QueryBuilder(test_db, Test).with_sorting(sort_by, sort_order).build()

    compiled = str(query.statement.compile(compile_kwargs={"literal_binds": True})).lower()
    assert f"left outer join {table} as {table}_1 on {table}_1.id = test.{foreign_key}" in compiled
    direction = " desc" if sort_order == "desc" else ""
    assert f"order by {table}_1.{column}{direction}, test.id" in compiled
    query.all()


def test_relationship_sort_coexists_with_eager_load_of_same_table(test_db):
    query = (
        QueryBuilder(test_db, Test)
        .with_related(include(Test.topic))
        .with_sorting("topic.name", "asc")
        .with_pagination(0, 10)
        .build()
    )

    compiled = str(query.statement.compile(compile_kwargs={"literal_binds": True})).lower()
    assert compiled.count("left outer join topic as") == 2
    query.all()


def test_apply_relationship_sort_keeps_query_unchanged_when_unsupported(test_db):
    query = test_db.query(Requirement)

    assert apply_virtual_relationship_sort(query, Requirement, "topic.name", "asc") is query


TEST_RUN_SORT_FIELDS = ["endpoint.name", "test_set.name"]


@pytest.mark.parametrize("sort_by", TEST_RUN_SORT_FIELDS)
def test_test_run_relationship_sort_validation(sort_by):
    assert is_virtual_relationship_sort(sort_by)
    assert model_supports_relationship_sort(TestRun, sort_by)
    validate_sort_field(TestRun, sort_by)
    with pytest.raises(HTTPException) as exc_info:
        validate_sort_field(Requirement, sort_by)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("sort_by", "table", "foreign_key"),
    [("endpoint.name", "endpoint", "endpoint_id"), ("test_set.name", "test_set", "test_set_id")],
)
@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_test_run_sort_joins_through_test_configuration(
    test_db, sort_by, table, foreign_key, sort_order
):
    query = QueryBuilder(test_db, TestRun).with_sorting(sort_by, sort_order).build()

    compiled = str(query.statement.compile(compile_kwargs={"literal_binds": True})).lower()
    assert (
        "left outer join test_configuration as test_configuration_1 "
        "on test_configuration_1.id = test_run.test_configuration_id" in compiled
    )
    assert (
        f"left outer join {table} as {table}_1 "
        f"on {table}_1.id = test_configuration_1.{foreign_key}" in compiled
    )
    direction = " desc" if sort_order == "desc" else ""
    assert f"order by {table}_1.name{direction}, test_run.id" in compiled
    query.all()

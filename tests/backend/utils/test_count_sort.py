import pytest
from fastapi import HTTPException

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.count_sort import (
    apply_virtual_count_sort,
    is_virtual_count_sort,
    model_supports_count_sort,
)
from rhesis.backend.app.utils.query_validation import validate_sort_field


def test_virtual_count_sort_detection():
    assert is_virtual_count_sort("comments_count")
    assert is_virtual_count_sort("tasks_count")
    assert is_virtual_count_sort("tags_count")
    assert not is_virtual_count_sort("created_at")


def test_model_supports_count_sort_for_test():
    assert model_supports_count_sort(Test, "comments_count")
    assert model_supports_count_sort(Test, "tasks_count")
    assert model_supports_count_sort(Test, "tags_count")


def test_validate_sort_field_accepts_virtual_counts():
    validate_sort_field(Test, "comments_count")
    validate_sort_field(Test, "tasks_count")
    validate_sort_field(Test, "tags_count")


def test_validate_sort_field_rejects_unknown_field():
    with pytest.raises(HTTPException) as exc_info:
        validate_sort_field(Test, "not_a_real_column")
    assert exc_info.value.status_code == 400


def test_apply_virtual_count_sort_builds_query(test_db):
    query = test_db.query(Test)
    sorted_query = apply_virtual_count_sort(
        query, Test, "comments_count", "desc"
    )
    compiled = str(sorted_query.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "comment" in compiled.lower()
    assert "count" in compiled.lower()


def test_tag_count_subquery_excludes_soft_deleted_links(test_db):
    query = test_db.query(Test)
    sorted_query = apply_virtual_count_sort(query, Test, "tags_count", "asc")
    compiled = str(sorted_query.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "deleted_at" in compiled.lower()

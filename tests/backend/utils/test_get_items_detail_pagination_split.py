"""Tests for the get_items_detail two-query pagination split.

get_items_detail resolves the page's IDs with a joinless query, then
eager-loads relationships scoped to just those IDs (crud_utils.py). These
tests verify the split preserves ordering, pagination boundaries, and
filtering semantics -- the correctness properties that would silently break
if the id-then-join re-assembly step regressed.

Categories are scoped with a unique name prefix per test and an explicit
OData filter, since the seeded test org already has its own default
categories that would otherwise interleave with sort order.
"""

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils import crud_utils
from tests.backend.routes.fixtures.data_factories import CategoryDataFactory

_PREFIX = "PagSplitTest_"


def _create_categories(db: Session, org_id: str, suffixes: list) -> list:
    return [
        crud_utils.create_item(
            db,
            models.Category,
            {**CategoryDataFactory.sample_data(), "name": f"{_PREFIX}{suffix}"},
            organization_id=org_id,
        )
        for suffix in suffixes
    ]


@pytest.mark.unit
@pytest.mark.utils
class TestGetItemsDetailPaginationSplit:
    def test_preserves_sort_order_across_pages(self, test_db: Session, test_org_id):
        created = _create_categories(
            test_db, test_org_id, ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
        )
        by_name = {c.name: c.id for c in created}
        scoped_filter = f"startswith(name,'{_PREFIX}')"

        page1 = crud_utils.get_items_detail(
            test_db,
            models.Category,
            skip=0,
            limit=2,
            sort_by="name",
            sort_order="asc",
            filter=scoped_filter,
            organization_id=test_org_id,
        )
        page2 = crud_utils.get_items_detail(
            test_db,
            models.Category,
            skip=2,
            limit=2,
            sort_by="name",
            sort_order="asc",
            filter=scoped_filter,
            organization_id=test_org_id,
        )

        assert [c.name for c in page1] == [f"{_PREFIX}Alpha", f"{_PREFIX}Bravo"]
        assert [c.name for c in page2] == [f"{_PREFIX}Charlie", f"{_PREFIX}Delta"]
        # No overlap between pages, and IDs match what was created.
        assert {c.id for c in page1} == {by_name[f"{_PREFIX}Alpha"], by_name[f"{_PREFIX}Bravo"]}

    def test_empty_result_returns_empty_list(self, test_db: Session, test_org_id):
        _create_categories(test_db, test_org_id, ["Solo"])

        results = crud_utils.get_items_detail(
            test_db,
            models.Category,
            skip=0,
            limit=10,
            filter=f"name eq '{_PREFIX}does-not-exist'",
            organization_id=test_org_id,
        )

        assert results == []

    def test_second_query_scoped_to_page_not_full_table(self, test_db: Session, test_org_id):
        """The join/eager-load query must hit only `limit` rows, not every
        matching row -- that's the entire point of the split. Assert this
        directly from SQL rather than inferring it from wall-clock time.
        """
        _create_categories(test_db, test_org_id, [f"Cat{i}" for i in range(10)])
        scoped_filter = f"startswith(name,'{_PREFIX}')"

        statements = []

        def _capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        test_engine = test_db.get_bind()
        event.listen(test_engine, "before_cursor_execute", _capture)
        try:
            results = crud_utils.get_items_detail(
                test_db,
                models.Category,
                skip=0,
                limit=3,
                sort_by="name",
                sort_order="asc",
                filter=scoped_filter,
                organization_id=test_org_id,
            )
        finally:
            event.remove(test_engine, "before_cursor_execute", _capture)

        assert len(results) == 3

        category_selects = [
            s for s in statements if "FROM category" in s and s.strip().upper().startswith("SELECT")
        ]
        # Phase 1 (id-only) + phase 2 (joined, scoped to those ids) both hit
        # the category table.
        assert len(category_selects) >= 2
        assert any("category.id IN" in s for s in category_selects)

"""Batched comment/task/file counts (``models/entity_counts.py``).

List and detail responses read ``counts`` from grouped COUNT queries instead of loading
every comment, task and file row. These tests pin that the numbers stay the same, that
soft-deleted and foreign-org rows are not counted, and that a row loaded without the
batch step still counts correctly.
"""

import time
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.crud.test import get_tests
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.entity_counts import attach_counts, batch_counts
from rhesis.backend.app.models.mixins import BATCHED_COUNTS_KEY
from rhesis.backend.app.scope import RequestScope, bind_scope, bypass_tenant_filter, reset_scope
from rhesis.backend.app.utils import crud_utils
from rhesis.backend.app.utils.query_utils import QueryBuilder
from tests.backend.routes.fixtures.data_factories import RequirementDataFactory, TestDataFactory

_NOW = datetime.now(timezone.utc)


def _create_test(db: Session, organization_id, user_id=None, **extra) -> models.Test:
    data = {**TestDataFactory.sample_data(), **extra}
    return crud_utils.create_item(
        db, models.Test, data, organization_id=str(organization_id), user_id=user_id
    )


def _comment(entity, organization_id, deleted=False) -> models.Comment:
    return models.Comment(
        content="c",
        entity_id=entity.id,
        entity_type=type(entity).__name__,
        organization_id=organization_id,
        deleted_at=_NOW if deleted else None,
    )


def _task(entity, organization_id, status_id, deleted=False) -> models.Task:
    return models.Task(
        title="t",
        status_id=status_id,
        entity_id=entity.id,
        entity_type=type(entity).__name__,
        organization_id=organization_id,
        deleted_at=_NOW if deleted else None,
    )


def _file(entity, organization_id, deleted=False) -> models.File:
    return models.File(
        filename="f.txt",
        content_type="text/plain",
        size_bytes=1,
        entity_id=entity.id,
        entity_type=type(entity).__name__,
        organization_id=organization_id,
        deleted_at=_NOW if deleted else None,
    )


def _add_activity(db, entity, organization_id, status_id, comments=0, tasks=0, files=0):
    db.add_all(
        [_comment(entity, organization_id) for _ in range(comments)]
        + [_task(entity, organization_id, status_id) for _ in range(tasks)]
        + [_file(entity, organization_id) for _ in range(files)]
    )


@pytest.mark.integration
class TestBatchedCounts:
    def test_list_route_skips_soft_deleted_rows(
        self, authenticated_client: TestClient, test_db: Session, test_org_id, db_status
    ):
        test = _create_test(test_db, test_org_id)
        _add_activity(test_db, test, test_org_id, db_status.id, comments=2, tasks=1, files=1)
        test_db.add_all(
            [
                _comment(test, test_org_id, deleted=True),
                _task(test, test_org_id, db_status.id, deleted=True),
                _file(test, test_org_id, deleted=True),
            ]
        )
        test_db.flush()

        response = authenticated_client.get("/tests/", params={"limit": 100})

        assert response.status_code == 200, response.text
        [row] = [t for t in response.json() if t["id"] == str(test.id)]
        assert row["counts"] == {"comments": 2, "tasks": 1, "files": 1}

    def test_counts_are_batched_not_loaded_and_match_the_relationship(
        self, test_db: Session, test_org_id, db_status
    ):
        requirement = crud_utils.create_item(
            test_db,
            models.Requirement,
            RequirementDataFactory.sample_data(),
            organization_id=test_org_id,
        )
        test = _create_test(test_db, test_org_id, requirement_id=requirement.id)
        _add_activity(test_db, test, test_org_id, db_status.id, comments=3, tasks=2, files=1)
        _add_activity(test_db, requirement, test_org_id, db_status.id, comments=1)
        test_db.flush()
        test_db.expire_all()

        listed = get_tests(test_db, limit=100, organization_id=test_org_id)
        [loaded] = [t for t in listed if t.id == test.id]

        # Counted in the batch, so the rows themselves were never loaded...
        for relationship in ("comments", "tasks", "files"):
            assert relationship in sa_inspect(loaded).unloaded
        assert loaded.counts == {"comments": 3, "tasks": 2, "files": 1}
        # ...and the loaded many-to-one relation was counted in the same batch.
        assert BATCHED_COUNTS_KEY in loaded.requirement.__dict__
        assert loaded.requirement.counts == {"comments": 1, "tasks": 0}

        # Expiring drops the batched numbers; the fallback counts the relationship.
        test_db.expire(loaded)
        assert BATCHED_COUNTS_KEY not in loaded.__dict__
        assert loaded.counts == {"comments": 3, "tasks": 2, "files": 1}

    def test_row_loaded_without_the_batch_counts_its_relationship(
        self, test_db: Session, test_org_id, db_status
    ):
        test = _create_test(test_db, test_org_id)
        _add_activity(test_db, test, test_org_id, db_status.id, comments=1, tasks=1)
        test_db.flush()
        test_db.expire_all()

        plain = test_db.get(models.Test, test.id)

        assert BATCHED_COUNTS_KEY not in plain.__dict__
        assert plain.counts == {"comments": 1, "tasks": 1, "files": 0}

    def test_keys_follow_the_model_mixins(self, test_db: Session, test_org_id, db_status):
        source = crud_utils.create_item(
            test_db, models.Source, {"title": "s"}, organization_id=test_org_id
        )
        _add_activity(test_db, source, test_org_id, db_status.id, comments=2)
        test_db.flush()

        attach_counts(test_db, [source])

        # Source has comments only: no tasks/files keys, same as the relationship path.
        assert source.counts == {"comments": 2}

    def test_counts_written_in_the_same_session_are_not_stale(
        self, test_db: Session, test_org_id, db_status
    ):
        test = _create_test(test_db, test_org_id)
        test_db.flush()
        test_db.expire_all()
        [loaded] = [
            t for t in get_tests(test_db, limit=100, organization_id=test_org_id) if t.id == test.id
        ]
        assert loaded.counts == {"comments": 0, "tasks": 0, "files": 0}

        _add_activity(test_db, loaded, test_org_id, db_status.id, comments=1)
        test_db.flush()

        # The flush drops the stale numbers, so the next list counts afresh.
        assert BATCHED_COUNTS_KEY not in loaded.__dict__
        [again] = [
            t for t in get_tests(test_db, limit=100, organization_id=test_org_id) if t.id == test.id
        ]
        assert again.counts == {"comments": 1, "tasks": 0, "files": 0}

    def test_multi_column_query_with_a_joined_collection_still_works(
        self, test_db: Session, test_org_id
    ):
        test = _create_test(test_db, test_org_id)
        test_db.flush()

        rows = (
            test_db.execute(
                select(models.Test, models.Test.id)
                .where(models.Test.id == test.id)
                .options(joinedload(models.Test.test_sets), batch_counts())
            )
            .unique()
            .all()
        )

        # Not a single-entity result, so the batch is skipped and nothing raises.
        assert [row[1] for row in rows] == [test.id]
        assert BATCHED_COUNTS_KEY not in rows[0][0].__dict__


@pytest.mark.security
def test_other_org_rows_are_not_counted(admin_test_db: Session, test_org_id):
    """Run as the superuser so only the ORM tenant filter keeps the orgs apart."""
    db = admin_test_db
    foreign_org = uuid.uuid4()
    db.execute(
        Base.metadata.tables["organization"]
        .insert()
        .values(id=foreign_org, name=f"Foreign {foreign_org.hex[:8]}", is_active=True)
    )
    test = _create_test(db, test_org_id)
    db.add_all([_comment(test, test_org_id), _comment(test, foreign_org)])
    db.flush()
    db.expire_all()

    token = bind_scope(RequestScope(organization_id=test_org_id))
    try:
        [scoped] = (
            QueryBuilder(db, models.Test)
            .with_default_derived_field_loads()
            .query.filter(models.Test.id == test.id)
            .all()
        )
        scoped_comments = scoped.counts["comments"]
    finally:
        reset_scope(token)

    with bypass_tenant_filter():
        attach_counts(db, [scoped])
        unscoped_comments = scoped.counts["comments"]

    assert scoped_comments == 1
    # The foreign row is really there: only the tenant filter left it out.
    assert unscoped_comments == 2


@pytest.mark.integration
def test_tests_list_counts_with_one_grouped_query_per_table(
    authenticated_client: TestClient, test_db: Session, test_org_id, db_status
):
    """GET /tests/?limit=50 over 50 busy tests; prints statements, rows and time with -s."""
    tests = []
    for _ in range(50):
        prompt = crud_utils.create_item(
            test_db, models.Prompt, {"content": "p"}, organization_id=test_org_id
        )
        test = _create_test(test_db, test_org_id, prompt_id=prompt.id)
        _add_activity(test_db, test, test_org_id, db_status.id, comments=3, tasks=2, files=1)
        _add_activity(test_db, prompt, test_org_id, db_status.id, comments=1)
        tests.append(test)
    test_db.flush()
    test_db.expire_all()

    statements = []

    def _capture(_conn, cursor, statement, *_args):
        statements.append((statement, max(cursor.rowcount, 0)))

    conn = test_db.connection()
    event.listen(conn, "after_cursor_execute", _capture)
    try:
        started = time.perf_counter()
        response = authenticated_client.get("/tests/", params={"limit": 50})
        elapsed_ms = (time.perf_counter() - started) * 1000
    finally:
        event.remove(conn, "after_cursor_execute", _capture)

    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in response.json()}
    for test in tests:
        assert rows[str(test.id)]["counts"] == {"comments": 3, "tasks": 2, "files": 1}
        assert rows[str(test.id)]["prompt"]["counts"] == {"comments": 1, "tasks": 0}

    sql = [" ".join(statement.split()) for statement, _rows in statements]
    # One grouped count per table covers the tests and their prompts; no row is loaded.
    for table in ("comment", "task", "file"):
        assert sum(f"count({table}.id)" in q for q in sql) == 1, table
    assert not any("comment.content" in q or "task.title" in q for q in sql)

    rows_read = sum(rows for _statement, rows in statements)
    print(f"\nGET /tests/?limit=50: {len(sql)} statements, {rows_read} rows, {elapsed_ms:.0f} ms")

"""Cached TestResult status ids."""

import uuid

import pytest
from sqlalchemy import event

from rhesis.backend.app.services import test_result_status
from rhesis.backend.app.utils.crud_utils import get_or_create_status


def _count(db, fn):
    seen = []

    def record(conn, cursor, statement, *args):
        if "set_config" not in statement and "SAVEPOINT" not in statement:
            seen.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        return fn(), len(seen)
    finally:
        event.remove(engine, "before_cursor_execute", record)


@pytest.mark.integration
class TestTestResultStatusId:
    def test_an_existing_status_is_read_once(self, test_db, test_organization):
        org = str(test_organization.id)
        name = f"Pass-{uuid.uuid4().hex[:6]}"
        status = get_or_create_status(test_db, name, "TestResult", organization_id=org)

        first, first_count = _count(
            test_db, lambda: test_result_status.test_result_status_id(test_db, org, name)
        )
        second, second_count = _count(
            test_db, lambda: test_result_status.test_result_status_id(test_db, org, name)
        )

        assert first == second == str(status.id)
        assert (first_count, second_count) == (1, 0)

    def test_a_status_created_here_is_not_cached(self, test_db, test_organization):
        org = str(test_organization.id)
        name = f"New-{uuid.uuid4().hex[:6]}"

        created = test_result_status.test_result_status_id(test_db, org, name)

        assert created is not None
        assert (org, name) not in test_result_status._status_ids._values

    def test_a_status_created_in_this_session_is_not_cached_on_a_later_call(
        self, test_db, test_organization
    ):
        org = str(test_organization.id)
        name = f"New-{uuid.uuid4().hex[:6]}"

        first = test_result_status.test_result_status_id(test_db, org, name)
        second = test_result_status.test_result_status_id(test_db, org, name)

        assert first == second
        assert (org, name) not in test_result_status._status_ids._values

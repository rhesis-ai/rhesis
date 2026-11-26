"""Loading a run's tests: one query for the tests, one for which have input files."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from rhesis.backend.app.models.file import File
from rhesis.backend.app.models.prompt import Prompt
from rhesis.backend.app.models.test import Test
from rhesis.backend.jobs.execution.batch.context import _prefetch_tests


def _make_tests(db, organization, user, status, count):
    tests = []
    for i in range(count):
        prompt = Prompt(
            content=f"prompt {i}",
            expected_response=f"expected {i}",
            language_code="en",
            user_id=user.id,
            organization_id=organization.id,
            status_id=status.id,
        )
        db.add(prompt)
        db.flush()
        test = Test(
            prompt_id=prompt.id,
            user_id=user.id,
            organization_id=organization.id,
            status_id=status.id,
        )
        db.add(test)
        tests.append(test)
    db.flush()
    return tests


def _statements(db, fn):
    seen = []

    def record(conn, cursor, statement, *args):
        if "set_config" not in statement and "SAVEPOINT" not in statement:
            seen.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return result, seen


@pytest.mark.integration
class TestPrefetchTests:
    def test_loads_each_test_with_its_prompt(self, test_db, test_organization, db_user, db_status):
        tests = _make_tests(test_db, test_organization, db_user, db_status, 3)

        test_data, with_files = _prefetch_tests(test_db, tests, str(test_organization.id))

        assert set(test_data) == {str(t.id) for t in tests}
        for i, test in enumerate(tests):
            entry = test_data[str(test.id)]
            assert entry["test"] is test
            assert (entry["prompt_content"], entry["expected_response"]) == (
                f"prompt {i}",
                f"expected {i}",
            )
        assert with_files == set()

    def test_query_count_does_not_grow_with_tests(
        self, test_db, test_organization, db_user, db_status
    ):
        org = str(test_organization.id)
        few = _make_tests(test_db, test_organization, db_user, db_status, 2)
        many = _make_tests(test_db, test_organization, db_user, db_status, 8)

        _, few_statements = _statements(test_db, lambda: _prefetch_tests(test_db, few, org))
        _, many_statements = _statements(test_db, lambda: _prefetch_tests(test_db, many, org))

        assert len(many_statements) == len(few_statements), many_statements

    def test_a_deleted_test_is_left_out(self, test_db, test_organization, db_user, db_status):
        kept, deleted = _make_tests(test_db, test_organization, db_user, db_status, 2)
        deleted.deleted_at = datetime.now(timezone.utc)
        test_db.flush()

        test_data, _ = _prefetch_tests(test_db, [kept, deleted], str(test_organization.id))

        assert set(test_data) == {str(kept.id)}

    def test_a_single_turn_test_without_a_prompt_is_left_out(
        self, test_db, test_organization, db_user, db_status
    ):
        (with_prompt,) = _make_tests(test_db, test_organization, db_user, db_status, 1)
        no_prompt = Test(
            user_id=db_user.id, organization_id=test_organization.id, status_id=db_status.id
        )
        test_db.add(no_prompt)
        test_db.flush()

        test_data, _ = _prefetch_tests(test_db, [with_prompt, no_prompt], str(test_organization.id))

        assert set(test_data) == {str(with_prompt.id)}

    def test_names_the_tests_with_stored_input_files(
        self, test_db, test_organization, db_user, db_status
    ):
        stored, pending, none = _make_tests(test_db, test_organization, db_user, db_status, 3)
        for test, path in ((stored, "files/a.pdf"), (pending, None)):
            test_db.add(
                File(
                    filename="a.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    entity_id=test.id,
                    entity_type="Test",
                    storage_path=path,
                    user_id=db_user.id,
                    organization_id=test_organization.id,
                )
            )
        test_db.flush()

        _, with_files = _prefetch_tests(test_db, [stored, pending, none], str(test_organization.id))

        assert with_files == {str(stored.id)}

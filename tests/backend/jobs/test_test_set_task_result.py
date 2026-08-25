"""Unit tests for ``_build_task_result`` in the test-set generation task.

Narrow by design: they only pin down that building the task result never
touches a lazy-loaded relationship on the ORM row, which is what broke
generation in practice.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm.exc import DetachedInstanceError

from rhesis.backend.jobs.test_set import _build_task_result


def _detached_test_set():
    """An ORM row whose relationship access raises, as a detached one does.

    Both save helpers return the row after their ``with
    self.get_db_session()`` block has closed, so ``.tests`` is unloaded on a
    session-less instance. Column attributes stay readable
    (``expire_on_commit=False``), which is why only the relationship blew up.
    """
    row = MagicMock()
    row.id = "ts-1"
    row.name = "Generated Set"
    row.description = "Auto-generated"
    row.short_description = "Short"
    row.attributes = {"metadata": {"generation": {"status": "completed"}}}
    type(row).tests = property(
        lambda _self: (_ for _ in ()).throw(
            DetachedInstanceError("Parent instance <TestSet> is not bound to a Session")
        )
    )
    return row


@pytest.mark.unit
class TestBuildTaskResult:
    def _build(self, db_test_set, tests_generated=7):
        return _build_task_result(
            MagicMock(),
            db_test_set,
            num_tests=10,
            synthesizer=MagicMock(),
            log_kwargs={},
            batch_size=5,
            org_id="org-1",
            user_id="user-1",
            tests_generated=tests_generated,
        )

    def test_does_not_touch_the_orm_relationship(self):
        """Regression: this raised DetachedInstanceError and failed the task
        *after* the tests had been written, leaving the test set marked
        ``generation.status = failed`` with a full set of tests behind it."""
        result = self._build(_detached_test_set())

        assert result["num_tests_generated"] == 7

    def test_reports_the_count_it_was_given(self):
        """The caller passes the SDK test set's own length, which is a plain
        list and needs no session."""
        result = self._build(_detached_test_set(), tests_generated=200)

        assert result["num_tests_generated"] == 200
        assert result["num_tests_requested"] == 10

    def test_still_reports_the_row_s_scalar_fields(self):
        result = self._build(_detached_test_set())

        assert result["test_set_id"] == "ts-1"
        assert result["test_set_name"] == "Generated Set"
        assert result["save_successful"] is True

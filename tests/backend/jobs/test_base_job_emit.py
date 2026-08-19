"""``BaseJob.emit()``: a narration call must never fail the job it narrates.

Found via a real regression: ``generate_and_save_owasp_test_set``'s tests use
non-UUID placeholder tenant ids ("org-1", "user-1"), and the first
``self.emit(...)`` call added for progress narration turned that placeholder
into a hard ``ValidationError`` that propagated out of the task. ``emit()``
now wraps its own body -- these tests pin that down directly rather than
relying on some other test's fixture data to catch it by accident.
"""

import logging
from unittest.mock import patch

from celery.utils.threads import LocalStack

from rhesis.backend.jobs.base import BaseJob


def _task(**request_kwargs) -> BaseJob:
    """A BaseJob instance with a real (unbound) request context, matching
    test_base_task.py's _real_base_task helper.
    """
    task = BaseJob()
    task.request_stack = LocalStack()
    task.push_request(id="task-1", retries=0, headers={}, kwargs={}, **request_kwargs)
    return task


class TestEmitIsDefensive:
    def test_invalid_organization_id_is_swallowed_not_raised(self, caplog):
        task = _task(organization_id="org-1", user_id="user-1", project_id="proj-1")

        with caplog.at_level(logging.WARNING):
            task.emit("Generating 5 tests")  # must not raise

        assert any("emit() failed" in r.message for r in caplog.records)

    def test_no_tenant_context_is_a_noop(self):
        task = _task()  # no organization_id at all

        with patch("rhesis.backend.events.emit") as mock_emit:
            task.emit("Generating 5 tests")

        mock_emit.assert_not_called()


class TestEmitHappyPath:
    def test_dispatches_an_activity_logged_event(self):
        task = _task(
            organization_id="11111111-1111-1111-1111-111111111111",
            user_id="22222222-2222-2222-2222-222222222222",
        )

        with patch("rhesis.backend.events.emit") as mock_emit:
            task.emit("Generated 5 of 5 tests", context={"count": 5})

        mock_emit.assert_called_once()
        (event,), _kwargs = mock_emit.call_args
        assert event.message == "Generated 5 of 5 tests"
        assert event.level == "info"
        assert event.context == {"count": 5}
        assert str(event.organization_id) == "11111111-1111-1111-1111-111111111111"

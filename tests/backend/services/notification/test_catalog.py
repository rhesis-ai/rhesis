"""Tests for the notification catalog's render functions.

Focused on the architect renderer, which is the only one that *declines*
(returns None): architect_chat_task runs several times per user request and
only the turn that concludes a background wait is a finished job.
"""

from unittest.mock import Mock

from rhesis.backend.app.constants import ARCHITECT_RESUME_PREFIX, EntityType
from rhesis.backend.app.models.enums import NotificationEventType, NotificationSection
from rhesis.backend.app.services.notification.catalog import (
    NOTIFICATION_CATALOG,
    _render_architect_plan_completed,
)

RESUME_MESSAGE = f"{ARCHITECT_RESUME_PREFIX} The background tasks have finished."


def _task(user_message: str, session_id: str = "session-1"):
    """A stand-in for the bound Celery task, which renderers read kwargs off."""
    task = Mock()
    task.request.kwargs = {"session_id": session_id, "user_message": user_message}
    task.request.headers = {}
    return task


class TestArchitectPlanCompletedRenderer:
    def test_declines_an_ordinary_interactive_turn(self):
        """The user is chatting live -- nothing to tell them about."""
        rendered = _render_architect_plan_completed(
            _task("Add tests for the login flow"),
            {"session_id": "session-1", "awaiting_task": False},
            None,
        )
        assert rendered is None

    def test_declines_a_turn_that_starts_a_wait(self):
        """awaiting_task means the long work is only just beginning."""
        rendered = _render_architect_plan_completed(
            _task(RESUME_MESSAGE),
            {"session_id": "session-1", "awaiting_task": True},
            None,
        )
        assert rendered is None

    def test_notifies_when_a_resume_turn_leaves_nothing_pending(self):
        rendered = _render_architect_plan_completed(
            _task(RESUME_MESSAGE),
            {"session_id": "session-1", "awaiting_task": False},
            None,
        )
        assert rendered is not None
        assert rendered.is_failure is False
        assert rendered.entity_id == "session-1"
        assert "Architect" in rendered.title

    def test_notifies_on_a_failed_resume_turn(self):
        """retval is normalized to {} on failure, so awaiting_task is absent."""
        rendered = _render_architect_plan_completed(_task(RESUME_MESSAGE), {}, "boom")
        assert rendered is not None
        assert rendered.is_failure is True
        assert rendered.entity_id == "session-1"

    def test_falls_back_to_kwargs_for_the_session_id(self):
        """The failure path has no retval to read session_id from."""
        rendered = _render_architect_plan_completed(
            _task(RESUME_MESSAGE, session_id="from-kwargs"), {}, "boom"
        )
        assert rendered is not None
        assert rendered.entity_id == "from-kwargs"


class TestArchitectCatalogEntry:
    def test_registered_under_the_architect_section(self):
        kind = NOTIFICATION_CATALOG[NotificationEventType.Architect.PLAN_COMPLETED]
        assert kind.section == NotificationSection.ARCHITECT
        assert kind.entity_type == EntityType.ARCHITECT_SESSION.value
        assert kind.render is _render_architect_plan_completed

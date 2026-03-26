"""Unit tests for trace metrics debounce cache and scheduling."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services.telemetry.trace_metrics_cache import (
    TraceMetricsDebounceCache,
    _cache,
    initialize_cache,  # noqa: F401
    is_conversation_complete,
    schedule_conversation_eval,
    signal_conversation_complete,
)


@pytest.fixture(autouse=True)
def clear_trace_metrics_debounce_cache():
    """Clear in-memory state and force in-memory mode for each test."""
    orig_redis = _cache._redis
    _cache._memory.clear()
    _cache._memory_timestamps.clear()
    _cache._redis = None
    yield
    _cache._memory.clear()
    _cache._memory_timestamps.clear()
    _cache._redis = orig_redis


@pytest.mark.unit
class TestTraceMetricsDebounceCache:
    """TraceMetricsDebounceCache behaviour in in-memory mode (no Redis)."""

    def test_register_returns_none_when_no_previous(self):
        assert isinstance(_cache, TraceMetricsDebounceCache)
        assert _cache.register_pending_eval("trace-1", "task-first") is None

    def test_register_returns_previous_task_id(self):
        _cache.register_pending_eval("trace-1", "task-a")
        previous = _cache.register_pending_eval("trace-1", "task-b")

        assert previous == "task-a"
        assert _cache.pop_pending_eval("trace-1") == "task-b"

    def test_pop_returns_task_id(self):
        _cache.register_pending_eval("trace-1", "task-x")

        assert _cache.pop_pending_eval("trace-1") == "task-x"

    def test_pop_returns_none_for_unknown(self):
        assert _cache.pop_pending_eval("unknown-trace") is None

    def test_pop_deletes_entry(self):
        _cache.register_pending_eval("trace-1", "task-y")
        assert _cache.pop_pending_eval("trace-1") == "task-y"
        assert _cache.pop_pending_eval("trace-1") is None

    def test_debounce_reset(self):
        """Second register yields first task id (caller revokes it)."""
        assert _cache.register_pending_eval("trace-1", "task-1") is None
        assert _cache.register_pending_eval("trace-1", "task-2") == "task-1"


@pytest.mark.unit
class TestScheduleConversationEval:
    """schedule_conversation_eval schedules Celery and revokes prior tasks."""

    def test_schedules_task(self):
        mock_result = MagicMock(id="new-task-id")
        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate."
                "evaluate_conversation_trace_metrics"
            ) as mock_task,
            patch("rhesis.backend.worker.app.control.revoke") as mock_revoke,
        ):
            mock_task.apply_async.return_value = mock_result
            schedule_conversation_eval(
                "trace-1",
                "project-1",
                "org-1",
                debounce_seconds=120,
            )

        mock_task.apply_async.assert_called_once_with(
            args=["trace-1", "project-1", "org-1"],
            countdown=120,
        )
        mock_revoke.assert_not_called()

    def test_revokes_previous_task(self):
        _cache.register_pending_eval("trace-1", "previous-celery-id")
        mock_result = MagicMock(id="new-task-id")
        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate."
                "evaluate_conversation_trace_metrics"
            ) as mock_task,
            patch("rhesis.backend.worker.app.control.revoke") as mock_revoke,
        ):
            mock_task.apply_async.return_value = mock_result
            schedule_conversation_eval("trace-1", "project-1", "org-1")

        mock_revoke.assert_called_once_with("previous-celery-id")


@pytest.mark.unit
class TestConversationComplete:
    """mark_complete / is_complete flag on TraceMetricsDebounceCache."""

    def test_is_complete_false_for_unknown(self):
        assert _cache.is_complete("unknown-trace") is False

    def test_mark_complete_sets_flag(self):
        _cache.mark_complete("trace-1")
        assert _cache.is_complete("trace-1") is True

    def test_is_complete_false_before_mark(self):
        assert _cache.is_complete("trace-1") is False

    def test_separate_traces_independent(self):
        _cache.mark_complete("trace-1")
        assert _cache.is_complete("trace-1") is True
        assert _cache.is_complete("trace-2") is False

    def test_module_level_helper(self):
        _cache.mark_complete("trace-1")
        assert is_conversation_complete("trace-1") is True
        assert is_conversation_complete("trace-other") is False


@pytest.mark.unit
class TestSignalConversationComplete:
    """signal_conversation_complete marks, revokes, and dispatches."""

    def test_marks_complete_and_dispatches(self):
        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate."
                "evaluate_conversation_trace_metrics"
            ) as mock_task,
            patch("rhesis.backend.worker.app.control.revoke") as mock_revoke,
        ):
            signal_conversation_complete("trace-1", "project-1", "org-1")

        assert _cache.is_complete("trace-1") is True
        mock_task.delay.assert_called_once_with(
            "trace-1", "project-1", "org-1"
        )
        mock_revoke.assert_not_called()

    def test_revokes_pending_task(self):
        _cache.register_pending_eval("trace-1", "old-celery-id")

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate."
                "evaluate_conversation_trace_metrics"
            ) as mock_task,
            patch("rhesis.backend.worker.app.control.revoke") as mock_revoke,
        ):
            signal_conversation_complete("trace-1", "project-1", "org-1")

        mock_revoke.assert_called_once_with("old-celery-id")
        mock_task.delay.assert_called_once_with(
            "trace-1", "project-1", "org-1"
        )
        assert _cache.is_complete("trace-1") is True
        assert _cache.pop_pending_eval("trace-1") is None

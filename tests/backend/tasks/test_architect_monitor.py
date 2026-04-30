"""Tests for the signal-based architect task monitoring."""

import json
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.tasks.architect_monitor import (
    _on_task_done,
    _resolve_awaiting_key,
    _resume_architect,
    _summarize_result,
    register_awaiting_tasks,
)

_CHAT_TASK_PATH = "rhesis.backend.tasks.architect.architect_chat_task"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    r = MagicMock()
    r.pipeline.return_value = r
    r.get.return_value = None
    r.exists.return_value = False
    r.scan_iter.return_value = []
    with patch(
        "rhesis.backend.tasks.architect_monitor._get_redis",
        return_value=r,
    ):
        yield r


# ---------------------------------------------------------------------------
# _summarize_result
# ---------------------------------------------------------------------------


class TestSummarizeResult:
    def test_successful_generation(self):
        summary = _summarize_result(
            "tid-1",
            "SUCCESS",
            {"test_set_id": "ts-1", "name": "Safety Tests", "test_count": 10},
        )
        assert "Safety Tests" in summary
        assert "10 tests" in summary
        assert "test_set_id=ts-1" in summary

    def test_successful_generation_alt_keys(self):
        summary = _summarize_result(
            "tid-1b",
            "SUCCESS",
            {"test_set_id": "ts-2", "test_set_name": "Accuracy", "num_tests_generated": 20},
        )
        assert "Accuracy" in summary
        assert "20 tests" in summary

    def test_successful_execution(self):
        summary = _summarize_result(
            "tid-2",
            "SUCCESS",
            {
                "test_run_id": "tr-1",
                "test_set_name": "Safety Tests",
                "total_tests": 10,
                "tests_passed": 8,
                "tests_failed": 2,
            },
        )
        assert "test_run_id=tr-1" in summary
        assert "Safety Tests" in summary
        assert "8 passed" in summary
        assert "2 failed" in summary

    def test_successful_execution_minimal(self):
        summary = _summarize_result("tid-2b", "SUCCESS", {"test_run_id": "tr-2"})
        assert "test_run_id=tr-2" in summary
        assert "completed" in summary

    def test_successful_generic_result(self):
        summary = _summarize_result("tid-3", "SUCCESS", {"some_key": "val"})
        assert "tid-3" in summary
        assert "completed" in summary

    def test_failed_result(self):
        summary = _summarize_result("tid-4", "FAILURE", "timeout")
        assert "tid-4" in summary
        assert "failed" in summary
        assert "timeout" in summary

    def test_failed_result_none(self):
        summary = _summarize_result("tid-5", "FAILURE", None)
        assert "unknown error" in summary


# ---------------------------------------------------------------------------
# register_awaiting_tasks
# ---------------------------------------------------------------------------


class TestRegisterAwaitingTasks:
    def test_stores_keys_in_redis(self, mock_redis):
        register_awaiting_tasks(
            session_id="sess-1",
            task_ids=["tid-a", "tid-b"],
            org_id="org-1",
            user_id="user-1",
            auto_approve=True,
        )

        pipe = mock_redis.pipeline.return_value
        set_calls = [c for c in pipe.method_calls if c[0] == "set"]
        assert len(set_calls) == 3  # 2 task keys + 1 count key

        count_call = set_calls[-1]
        assert count_call[1][0] == "arch:count:sess-1"
        assert count_call[1][1] == 2

        pipe.execute.assert_called_once()

    def test_context_includes_session_info(self, mock_redis):
        register_awaiting_tasks(
            session_id="sess-2",
            task_ids=["tid-c"],
            org_id="org-2",
            user_id="user-2",
        )

        pipe = mock_redis.pipeline.return_value
        set_calls = [c for c in pipe.method_calls if c[0] == "set"]
        ctx = json.loads(set_calls[0][1][1])
        assert ctx["session_id"] == "sess-2"
        assert ctx["org_id"] == "org-2"
        assert ctx["user_id"] == "user-2"
        assert ctx["auto_approve"] is False


# ---------------------------------------------------------------------------
# _resolve_awaiting_key
# ---------------------------------------------------------------------------


class TestResolveAwaitingKey:
    def test_direct_task_id_match(self, mock_redis):
        mock_redis.exists.return_value = True
        key = _resolve_awaiting_key(mock_redis, "tid-1", {})
        assert key == "arch:task:tid-1"

    def test_no_match_returns_none(self, mock_redis):
        mock_redis.exists.return_value = False
        key = _resolve_awaiting_key(mock_redis, "tid-1", {})
        assert key is None

    def test_fallback_to_test_run_id_with_execution_status(self, mock_redis):
        """collect_results returns execution_status — triggers fallback."""
        def _exists(key):
            return key == "arch:task:tr-run-1"

        mock_redis.exists.side_effect = _exists
        key = _resolve_awaiting_key(
            mock_redis,
            "collect-xyz",
            {
                "test_run_id": "tr-run-1",
                "execution_status": "Complete",
                "tests_passed": 8,
            },
        )
        assert key == "arch:task:tr-run-1"

    def test_no_fallback_without_execution_status(self, mock_redis):
        """execute_test_configuration also has test_run_id but no
        execution_status — must NOT match to avoid premature resume."""
        def _exists(key):
            return key == "arch:task:tr-run-1"

        mock_redis.exists.side_effect = _exists
        key = _resolve_awaiting_key(
            mock_redis,
            "parent-task-xyz",
            {"test_run_id": "tr-run-1", "execution_mode": "parallel"},
        )
        assert key is None

    def test_no_fallback_when_retval_not_dict(self, mock_redis):
        mock_redis.exists.return_value = False
        key = _resolve_awaiting_key(mock_redis, "tid-1", "string-result")
        assert key is None

    def test_no_fallback_when_test_run_id_absent(self, mock_redis):
        mock_redis.exists.return_value = False
        key = _resolve_awaiting_key(mock_redis, "tid-1", {"other": "val"})
        assert key is None


# ---------------------------------------------------------------------------
# _on_task_done signal handler
# ---------------------------------------------------------------------------


class TestOnTaskDone:
    def test_ignores_non_awaited_tasks(self, mock_redis):
        mock_redis.exists.return_value = False
        _on_task_done(task_id="random-task", state="SUCCESS", retval={})
        mock_redis.decr.assert_not_called()

    def test_ignores_none_task_id(self, mock_redis):
        _on_task_done(task_id=None, state="SUCCESS", retval={})
        mock_redis.exists.assert_not_called()

    def test_decrements_counter_on_direct_task_match(self, mock_redis):
        ctx = json.dumps({
            "session_id": "sess-1",
            "org_id": "org-1",
            "user_id": "user-1",
            "auto_approve": False,
        })
        mock_redis.exists.return_value = True
        mock_redis.get.return_value = ctx.encode()
        mock_redis.decr.return_value = 1

        _on_task_done(
            task_id="tid-a",
            state="SUCCESS",
            retval={"test_set_id": "ts-1", "name": "X", "test_count": 5},
        )

        mock_redis.delete.assert_called_with("arch:task:tid-a")
        mock_redis.set.assert_called_once()
        result_key = mock_redis.set.call_args[0][0]
        assert result_key == "arch:result:sess-1:tid-a"
        mock_redis.decr.assert_called_once_with("arch:count:sess-1")

    @patch("rhesis.backend.tasks.architect_monitor._resume_architect")
    def test_matches_via_test_run_id_in_result(
        self, mock_resume, mock_redis
    ):
        """collect_results carries test_run_id — match via alt key."""
        ctx = json.dumps({
            "session_id": "sess-1",
            "org_id": "org-1",
            "user_id": "user-1",
            "auto_approve": False,
        })

        def _exists_side_effect(key):
            return key == "arch:task:tr-run-1"

        mock_redis.exists.side_effect = _exists_side_effect
        mock_redis.get.return_value = ctx.encode()
        mock_redis.decr.return_value = 0

        _on_task_done(
            task_id="collect-task-xyz",
            state="SUCCESS",
            retval={
                "test_run_id": "tr-run-1",
                "execution_status": "Complete",
                "tests_passed": 4,
                "tests_failed": 6,
            },
        )

        mock_redis.delete.assert_called_with("arch:task:tr-run-1")
        mock_redis.decr.assert_called_once_with("arch:count:sess-1")
        mock_resume.assert_called_once()

    @patch("rhesis.backend.tasks.architect_monitor._resume_architect")
    def test_resumes_when_counter_hits_zero(self, mock_resume, mock_redis):
        ctx = json.dumps({
            "session_id": "sess-1",
            "org_id": "org-1",
            "user_id": "user-1",
            "auto_approve": True,
        })
        mock_redis.exists.return_value = True
        mock_redis.get.return_value = ctx.encode()
        mock_redis.decr.return_value = 0

        _on_task_done(task_id="tid-last", state="SUCCESS", retval={})

        mock_resume.assert_called_once()
        call_args = mock_resume.call_args
        assert call_args[0][0] == "sess-1"
        assert call_args[0][1]["auto_approve"] is True

    @patch("rhesis.backend.tasks.architect_monitor._resume_architect")
    def test_does_not_resume_while_tasks_remain(self, mock_resume, mock_redis):
        ctx = json.dumps({
            "session_id": "sess-1",
            "org_id": "org-1",
            "user_id": "user-1",
            "auto_approve": False,
        })
        mock_redis.exists.return_value = True
        mock_redis.get.return_value = ctx.encode()
        mock_redis.decr.return_value = 2

        _on_task_done(task_id="tid-first", state="SUCCESS", retval={})

        mock_resume.assert_not_called()

    def test_stores_failed_task_result(self, mock_redis):
        ctx = json.dumps({
            "session_id": "sess-1",
            "org_id": "org-1",
            "user_id": "user-1",
            "auto_approve": False,
        })
        mock_redis.exists.return_value = True
        mock_redis.get.return_value = ctx.encode()
        mock_redis.decr.return_value = 1

        _on_task_done(task_id="tid-f", state="FAILURE", retval="LLM timeout")

        stored = json.loads(mock_redis.set.call_args[0][1])
        assert stored["state"] == "FAILURE"
        assert stored["result"] == "LLM timeout"


# ---------------------------------------------------------------------------
# _resume_architect
# ---------------------------------------------------------------------------


class TestResumeArchitect:
    @patch(_CHAT_TASK_PATH)
    def test_dispatches_architect_with_results(self, mock_chat_task, mock_redis):
        mock_redis.scan_iter.return_value = [
            b"arch:result:sess-1:tid-a",
            b"arch:result:sess-1:tid-b",
        ]
        mock_redis.get.side_effect = [
            json.dumps({
                "task_id": "tid-a",
                "state": "SUCCESS",
                "result": {"test_set_id": "ts-1", "name": "Set A", "test_count": 5},
            }).encode(),
            json.dumps({
                "task_id": "tid-b",
                "state": "SUCCESS",
                "result": {"test_run_id": "tr-1"},
            }).encode(),
        ]

        context = {
            "session_id": "sess-1",
            "org_id": "org-1",
            "user_id": "user-1",
            "auto_approve": True,
        }

        _resume_architect("sess-1", context, mock_redis)

        mock_chat_task.apply_async.assert_called_once()
        kw = mock_chat_task.apply_async.call_args.kwargs
        msg = kw["kwargs"]["user_message"]
        assert "[TASK_COMPLETED]" in msg
        assert "Set A" in msg
        assert "test_run_id=tr-1" in msg
        assert kw["kwargs"]["auto_approve"] is True
        assert kw["headers"]["organization_id"] == "org-1"

    @patch(_CHAT_TASK_PATH)
    def test_cleans_up_redis_keys(self, mock_chat_task, mock_redis):
        mock_redis.scan_iter.return_value = [b"arch:result:sess-2:tid-x"]
        mock_redis.get.return_value = json.dumps({
            "task_id": "tid-x",
            "state": "SUCCESS",
            "result": {},
        }).encode()

        _resume_architect(
            "sess-2",
            {"session_id": "sess-2", "org_id": "", "user_id": ""},
            mock_redis,
        )

        delete_calls = [
            c for c in mock_redis.method_calls if c[0] == "delete"
        ]
        deleted_keys = [c[1][0] for c in delete_calls]
        assert b"arch:result:sess-2:tid-x" in deleted_keys
        assert "arch:count:sess-2" in deleted_keys

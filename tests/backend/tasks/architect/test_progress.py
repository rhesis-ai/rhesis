"""Unit tests for the architect_progress helper.

The helper is the bridge that lets background workers publish live
progress events to the architect chat session that is awaiting them.
Tests assert the Redis lookup, the published payload shape, and the
silent no-op fallback when no architect session is awaiting.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# lookup_session_for_task
# ---------------------------------------------------------------------------


class TestLookupSessionForTask:
    @patch("rhesis.backend.tasks.architect.progress._get_redis")
    def test_returns_session_id_when_key_present(self, mock_get_redis):
        from rhesis.backend.tasks.architect.progress import lookup_session_for_task

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(
            {"session_id": "sess-123", "org_id": "org-1", "user_id": "user-1"}
        )
        mock_get_redis.return_value = mock_redis

        assert lookup_session_for_task("task-abc") == "sess-123"
        mock_redis.get.assert_called_once_with("arch:task:task-abc")

    @patch("rhesis.backend.tasks.architect.progress._get_redis")
    def test_returns_none_when_key_missing(self, mock_get_redis):
        from rhesis.backend.tasks.architect.progress import lookup_session_for_task

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        assert lookup_session_for_task("task-missing") is None

    @patch("rhesis.backend.tasks.architect.progress._get_redis")
    def test_returns_none_on_invalid_json(self, mock_get_redis):
        from rhesis.backend.tasks.architect.progress import lookup_session_for_task

        mock_redis = MagicMock()
        mock_redis.get.return_value = b"not-valid-json"
        mock_get_redis.return_value = mock_redis

        assert lookup_session_for_task("task-bad") is None

    @patch("rhesis.backend.tasks.architect.progress._get_redis")
    def test_returns_none_when_session_id_missing(self, mock_get_redis):
        from rhesis.backend.tasks.architect.progress import lookup_session_for_task

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"org_id": "org-1"})
        mock_get_redis.return_value = mock_redis

        assert lookup_session_for_task("task-no-sid") is None

    @patch("rhesis.backend.tasks.architect.progress._get_redis")
    def test_returns_none_on_redis_failure(self, mock_get_redis):
        from rhesis.backend.tasks.architect.progress import lookup_session_for_task

        mock_get_redis.side_effect = RuntimeError("redis down")

        assert lookup_session_for_task("task-x") is None


# ---------------------------------------------------------------------------
# publish_task_progress
# ---------------------------------------------------------------------------


class TestPublishTaskProgress:
    @patch("rhesis.backend.tasks.architect.progress.publish_event")
    @patch("rhesis.backend.tasks.architect.progress.lookup_session_for_task")
    def test_publishes_to_session_channel(self, mock_lookup, mock_publish):
        from rhesis.backend.app.schemas.websocket import (
            ChannelTarget,
            EventType,
        )
        from rhesis.backend.tasks.architect.progress import publish_task_progress

        mock_lookup.return_value = "sess-1"

        publish_task_progress(
            task_id="task-1",
            status="progress",
            label="Running domain probing strategy",
        )

        assert mock_publish.call_count == 1
        message, target = mock_publish.call_args.args
        assert message.type == EventType.ARCHITECT_TASK_PROGRESS
        assert message.payload == {
            "session_id": "sess-1",
            "task_id": "task-1",
            "status": "progress",
            "label": "Running domain probing strategy",
        }
        assert isinstance(target, ChannelTarget)
        assert target.channel == "architect:sess-1"

    @patch("rhesis.backend.tasks.architect.progress.publish_event")
    @patch("rhesis.backend.tasks.architect.progress.lookup_session_for_task")
    def test_includes_optional_fields_when_provided(self, mock_lookup, mock_publish):
        from rhesis.backend.tasks.architect.progress import publish_task_progress

        mock_lookup.return_value = "sess-1"
        publish_task_progress(
            task_id="task-1",
            status="completed",
            label="Done",
            step=3,
            total=8,
            duration_ms=1234,
        )

        payload = mock_publish.call_args.args[0].payload
        assert payload["step"] == 3
        assert payload["total"] == 8
        assert payload["duration_ms"] == 1234

    @patch("rhesis.backend.tasks.architect.progress.publish_event")
    @patch("rhesis.backend.tasks.architect.progress.lookup_session_for_task")
    def test_skips_optional_fields_when_omitted(self, mock_lookup, mock_publish):
        from rhesis.backend.tasks.architect.progress import publish_task_progress

        mock_lookup.return_value = "sess-1"
        publish_task_progress(task_id="t", status="started", label="Hi")

        payload = mock_publish.call_args.args[0].payload
        for key in ("step", "total", "duration_ms"):
            assert key not in payload, f"{key} should not be set when not provided"

    @patch("rhesis.backend.tasks.architect.progress.publish_event")
    @patch("rhesis.backend.tasks.architect.progress.lookup_session_for_task")
    def test_silent_noop_when_no_session(self, mock_lookup, mock_publish):
        from rhesis.backend.tasks.architect.progress import publish_task_progress

        mock_lookup.return_value = None
        publish_task_progress(
            task_id="task-x",
            status="started",
            label="Anything",
        )
        mock_publish.assert_not_called()

    @patch("rhesis.backend.tasks.architect.progress.publish_event")
    @patch("rhesis.backend.tasks.architect.progress.lookup_session_for_task")
    def test_skips_lookup_when_session_id_provided(self, mock_lookup, mock_publish):
        from rhesis.backend.tasks.architect.progress import publish_task_progress

        publish_task_progress(
            task_id="task-1",
            status="progress",
            label="Working",
            session_id="sess-cached",
        )
        mock_lookup.assert_not_called()
        assert mock_publish.call_count == 1
        assert mock_publish.call_args.args[0].payload["session_id"] == "sess-cached"

    @patch("rhesis.backend.tasks.architect.progress.publish_event")
    @patch("rhesis.backend.tasks.architect.progress.lookup_session_for_task")
    def test_swallows_publisher_failures(self, mock_lookup, mock_publish):
        from rhesis.backend.tasks.architect.progress import publish_task_progress

        mock_lookup.return_value = "sess-1"
        mock_publish.side_effect = ConnectionError("redis cluster down")

        publish_task_progress(task_id="t", status="started", label="L")


# ---------------------------------------------------------------------------
# Integration with run_exploration_task
# ---------------------------------------------------------------------------


class TestExplorationEmitsProgress:
    """run_exploration_task forwards milestones to ``publish_task_progress``.

    The task no longer caches the architect session id at start (that
    was racy — ``register_awaiting_tasks`` typically runs after the
    explore task has already been picked up by a worker). Instead it
    delegates session resolution to ``publish_task_progress`` on every
    call, so these tests just verify the pipe-through.
    """

    @patch("rhesis.backend.tasks.endpoint.explore.publish_task_progress")
    @patch("rhesis.sdk.async_utils.run_sync")
    @patch("rhesis.sdk.agents.tools.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    @patch("rhesis.backend.tasks.endpoint.explore.get_user_generation_model")
    @patch("rhesis.backend.tasks.endpoint.explore.crud")
    def test_publishes_started_progress_and_completed(
        self,
        mock_crud,
        mock_get_model,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
        mock_publish,
    ):
        from rhesis.backend.tasks.endpoint.explore import run_exploration_task

        mock_crud.get_user.return_value = MagicMock()
        mock_get_model.return_value = "vertex_ai/gemini-2.0-flash"
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result_mock = MagicMock()
        result_mock.success = True
        result_mock.content = json.dumps({"findings": {}, "conversation": []})
        result_mock.error = None
        mock_asyncio_run.return_value = result_mock

        with (
            patch.object(
                run_exploration_task,
                "get_tenant_context",
                return_value=("org-1", "user-1", None),
            ),
            patch.object(run_exploration_task, "update_state"),
            patch.object(
                run_exploration_task.request,
                "id",
                "task-abc",
                create=True,
            ),
        ):
            run_exploration_task.run(endpoint_id="ep-uuid", strategy="domain_probing")

        statuses = [call.kwargs.get("status") for call in mock_publish.call_args_list]
        assert "started" in statuses
        assert "progress" in statuses
        assert "completed" in statuses
        assert all("session_id" not in call.kwargs for call in mock_publish.call_args_list)
        assert all(call.kwargs.get("task_id") == "task-abc" for call in mock_publish.call_args_list)

    @patch("rhesis.backend.tasks.endpoint.explore.publish_task_progress")
    @patch("rhesis.sdk.async_utils.run_sync")
    @patch("rhesis.sdk.agents.tools.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    @patch("rhesis.backend.tasks.endpoint.explore.get_user_generation_model")
    @patch("rhesis.backend.tasks.endpoint.explore.crud")
    def test_skips_emission_when_task_id_is_empty(
        self,
        mock_crud,
        mock_get_model,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
        mock_publish,
    ):
        from rhesis.backend.tasks.endpoint.explore import run_exploration_task

        mock_crud.get_user.return_value = MagicMock()
        mock_get_model.return_value = "vertex_ai/gemini-2.0-flash"
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result_mock = MagicMock()
        result_mock.success = True
        result_mock.content = json.dumps({"findings": {}, "conversation": []})
        result_mock.error = None
        mock_asyncio_run.return_value = result_mock

        with (
            patch.object(
                run_exploration_task,
                "get_tenant_context",
                return_value=("org-1", "user-1", None),
            ),
            patch.object(run_exploration_task, "update_state"),
        ):
            run_exploration_task.run(endpoint_id="ep-uuid", strategy="domain_probing")

        mock_publish.assert_not_called()

    @patch("rhesis.backend.tasks.endpoint.explore.publish_task_progress")
    @patch("rhesis.sdk.async_utils.run_sync")
    @patch("rhesis.sdk.agents.tools.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    @patch("rhesis.backend.tasks.endpoint.explore.get_user_generation_model")
    @patch("rhesis.backend.tasks.endpoint.explore.crud")
    def test_emits_failed_event_when_tool_reports_failure(
        self,
        mock_crud,
        mock_get_model,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
        mock_publish,
    ):
        from rhesis.backend.tasks.endpoint.explore import run_exploration_task

        mock_crud.get_user.return_value = MagicMock()
        mock_get_model.return_value = "vertex_ai/gemini-2.0-flash"
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result_mock = MagicMock()
        result_mock.success = False
        result_mock.content = ""
        result_mock.error = "Endpoint unreachable"
        mock_asyncio_run.return_value = result_mock

        with (
            patch.object(
                run_exploration_task,
                "get_tenant_context",
                return_value=("org-1", "user-1", None),
            ),
            patch.object(run_exploration_task, "update_state"),
            patch.object(
                run_exploration_task.request,
                "id",
                "task-abc",
                create=True,
            ),
        ):
            with pytest.raises(RuntimeError):
                run_exploration_task.run(endpoint_id="ep-uuid", strategy="domain_probing")

        statuses = [call.kwargs.get("status") for call in mock_publish.call_args_list]
        assert "failed" in statuses


# ---------------------------------------------------------------------------
# Penelope progress handler
# ---------------------------------------------------------------------------


class TestPenelopeProgressHandler:
    @pytest.mark.asyncio
    async def test_emits_per_turn_progress_for_user_facing_tools(self):
        from rhesis.backend.tasks.endpoint.explore import _PenelopeProgressHandler

        emitted: list = []

        def emit(status, label, **kwargs):
            emitted.append({"status": status, "label": label, **kwargs})

        handler = _PenelopeProgressHandler(emit)
        await handler.on_tool_start(
            tool_name="send_message_to_target",
            arguments={"message": "What can you do?"},
        )
        await handler.on_tool_start(
            tool_name="send_message_to_target",
            arguments={"message": "Can you book me a flight?"},
        )

        assert len(emitted) == 2
        assert emitted[0]["status"] == "progress"
        assert emitted[0]["step"] == 1
        assert "What can you do?" in emitted[0]["label"]
        assert emitted[1]["step"] == 2

    @pytest.mark.asyncio
    async def test_skips_non_user_facing_tools(self):
        from rhesis.backend.tasks.endpoint.explore import _PenelopeProgressHandler

        emitted: list = []
        handler = _PenelopeProgressHandler(lambda *a, **kw: emitted.append((a, kw)))

        await handler.on_tool_start(tool_name="analyze_response", arguments={})
        await handler.on_tool_start(tool_name="record_finding", arguments={"text": "..."})

        assert emitted == [], "internal Penelope tools should not surface as progress"

    @pytest.mark.asyncio
    async def test_truncates_long_probe_messages(self):
        from rhesis.backend.tasks.endpoint.explore import _PenelopeProgressHandler

        emitted: list = []

        def emit(status, label, **kwargs):
            emitted.append(label)

        handler = _PenelopeProgressHandler(emit)
        long_message = "Please " + "tell me more " * 50
        await handler.on_tool_start(
            tool_name="send_message_to_target",
            arguments={"message": long_message},
        )

        assert len(emitted[0]) < len(long_message) / 2

    @pytest.mark.asyncio
    async def test_on_tool_end_is_a_noop(self):
        from rhesis.backend.tasks.endpoint.explore import _PenelopeProgressHandler

        emitted: list = []
        handler = _PenelopeProgressHandler(lambda *a, **kw: emitted.append(a))

        await handler.on_tool_end(
            tool_name="send_message_to_target",
            result=MagicMock(success=True),
        )

        assert emitted == []


# ---------------------------------------------------------------------------
# project_id flow through exploration task
# ---------------------------------------------------------------------------


class TestExplorationProjectIdFlow:
    """Verify that project_id from tenant context flows to make_target_factory."""

    @patch("rhesis.backend.tasks.endpoint.explore.publish_task_progress")
    @patch("rhesis.sdk.async_utils.run_sync")
    @patch("rhesis.sdk.agents.tools.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    @patch("rhesis.backend.tasks.endpoint.explore.get_user_generation_model")
    @patch("rhesis.backend.tasks.endpoint.explore.crud")
    def test_passes_project_id_to_target_factory(
        self,
        mock_crud,
        mock_get_model,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
        mock_publish,
    ):
        from rhesis.backend.tasks.endpoint.explore import run_exploration_task

        mock_crud.get_user.return_value = MagicMock()
        mock_get_model.return_value = "vertex_ai/gemini-2.0-flash"
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result_mock = MagicMock()
        result_mock.success = True
        result_mock.content = json.dumps({"findings": {}, "conversation": []})
        result_mock.error = None
        mock_asyncio_run.return_value = result_mock

        with (
            patch.object(
                run_exploration_task,
                "get_tenant_context",
                return_value=("org-1", "user-1", "proj-1"),
            ),
            patch.object(run_exploration_task, "update_state"),
            patch.object(
                run_exploration_task.request,
                "id",
                "task-abc",
                create=True,
            ),
        ):
            run_exploration_task.run(endpoint_id="ep-uuid", strategy="domain_probing")

        mock_make_factory.assert_called_once_with(
            org_id="org-1",
            user_id="user-1",
            db=mock_db_ctx.return_value.__enter__.return_value,
            project_id="proj-1",
        )

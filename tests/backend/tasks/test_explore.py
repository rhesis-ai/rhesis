"""Unit tests for run_exploration_task and make_target_factory."""

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_result(success: bool = True, content: dict | None = None, error: str | None = None):
    result = MagicMock()
    result.success = success
    result.content = json.dumps(content or {"findings": {}, "conversation": [], "status": "done"})
    result.error = error
    return result


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestRunExplorationTaskSuccess:
    @patch("rhesis.backend.tasks.endpoint.explore.asyncio.run")
    @patch("rhesis.sdk.agents.tools.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    @patch("rhesis.backend.tasks.endpoint.explore.get_user_generation_model")
    @patch("rhesis.backend.tasks.endpoint.explore.crud")
    def test_returns_findings_dict(
        self,
        mock_crud,
        mock_get_model,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
    ):
        """Successful run should return a dict containing endpoint_id and strategy."""
        from rhesis.backend.tasks.endpoint.explore import run_exploration_task

        mock_crud.get_user.return_value = MagicMock()
        mock_get_model.return_value = "vertex_ai/gemini-2.0-flash"
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_asyncio_run.return_value = _make_tool_result(
            success=True,
            content={"findings": {"domain": "travel"}, "conversation": [], "status": "done"},
        )

        with (
            patch.object(run_exploration_task, "get_tenant_context", return_value=("org-1", "user-1")),
            patch.object(run_exploration_task, "update_state"),
        ):
            result = run_exploration_task.run(endpoint_id="ep-uuid", strategy="domain_probing")

        assert result["endpoint_id"] == "ep-uuid"
        assert result["strategy"] == "domain_probing"
        assert "duration_ms" in result

    @patch("rhesis.backend.tasks.endpoint.explore.asyncio.run")
    @patch("rhesis.sdk.agents.tools.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    @patch("rhesis.backend.tasks.endpoint.explore.get_user_generation_model")
    @patch("rhesis.backend.tasks.endpoint.explore.crud")
    def test_update_state_called(
        self,
        mock_crud,
        mock_get_model,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
    ):
        """update_state should be called at least twice (start + strategy PROGRESS)."""
        from rhesis.backend.tasks.endpoint.explore import run_exploration_task

        mock_crud.get_user.return_value = MagicMock()
        mock_get_model.return_value = "vertex_ai/gemini-2.0-flash"
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_asyncio_run.return_value = _make_tool_result(success=True)

        mock_update_state = MagicMock()
        with (
            patch.object(run_exploration_task, "get_tenant_context", return_value=("org-1", "user-1")),
            patch.object(run_exploration_task, "update_state", mock_update_state),
        ):
            run_exploration_task.run(endpoint_id="ep-uuid", strategy="capability_mapping")

        assert mock_update_state.call_count >= 2


# ---------------------------------------------------------------------------
# Failure path
# ---------------------------------------------------------------------------


class TestRunExplorationTaskFailure:
    @patch("rhesis.backend.tasks.endpoint.explore.asyncio.run")
    @patch("rhesis.sdk.agents.tools.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    @patch("rhesis.backend.tasks.endpoint.explore.get_user_generation_model")
    @patch("rhesis.backend.tasks.endpoint.explore.crud")
    def test_raises_on_tool_failure(
        self,
        mock_crud,
        mock_get_model,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
    ):
        """When ExploreEndpointTool reports failure, task should raise RuntimeError."""
        from rhesis.backend.tasks.endpoint.explore import run_exploration_task

        mock_crud.get_user.return_value = MagicMock()
        mock_get_model.return_value = "vertex_ai/gemini-2.0-flash"
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_asyncio_run.return_value = _make_tool_result(success=False, error="Endpoint unreachable")

        with (
            patch.object(run_exploration_task, "get_tenant_context", return_value=("org-1", "user-1")),
            patch.object(run_exploration_task, "update_state"),
        ):
            with pytest.raises(RuntimeError, match="Endpoint unreachable"):
                run_exploration_task.run(endpoint_id="ep-uuid", strategy="domain_probing")

    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    @patch("rhesis.backend.tasks.endpoint.explore.crud")
    def test_raises_when_user_not_found(self, mock_crud, mock_db_ctx):
        """Task should raise when the user cannot be resolved."""
        from rhesis.backend.tasks.endpoint.explore import run_exploration_task

        mock_crud.get_user.return_value = None
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(run_exploration_task, "get_tenant_context", return_value=("org-1", "user-1")),
            patch.object(run_exploration_task, "update_state"),
        ):
            with pytest.raises(RuntimeError, match="User .* not found"):
                run_exploration_task.run(endpoint_id="ep-uuid", strategy="domain_probing")


# ---------------------------------------------------------------------------
# make_target_factory
# ---------------------------------------------------------------------------


class TestMakeTargetFactory:
    def test_factory_creates_backend_endpoint_target(self):
        """make_target_factory should return a callable that creates BackendEndpointTarget."""
        from unittest.mock import patch

        from rhesis.backend.tasks.endpoint.target import make_target_factory
        from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget

        mock_db = MagicMock()
        factory = make_target_factory(org_id="org-1", user_id="user-1", db=mock_db)
        assert callable(factory)

        with patch.object(BackendEndpointTarget, "__init__", return_value=None) as mock_init:
            factory("ep-uuid")
            mock_init.assert_called_once_with(
                db=mock_db,
                endpoint_id="ep-uuid",
                organization_id="org-1",
                user_id="user-1",
            )

"""Unit tests for run_exploration_task.

Tests the happy path (SUCCESS), failure propagation (FAILURE), and
progress state updates without requiring a real Celery broker, database,
or Penelope/ExploreEndpointTool process.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _make_task(org_id: str = "org-1", user_id: str = "user-1"):
    """Return a bound task instance with mocked Celery internals."""
    from rhesis.backend.tasks.endpoint.explore import run_exploration_task

    task = run_exploration_task
    mock_self = MagicMock()
    mock_self.get_tenant_context.return_value = (org_id, user_id)
    mock_self.update_state = MagicMock()
    return task, mock_self


def _make_tool_result(success: bool = True, content: dict | None = None, error: str | None = None):
    """Return a fake ToolResult-like object."""
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
    @patch("rhesis.backend.tasks.endpoint.explore.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    def test_returns_findings_dict(
        self,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
    ):
        """Successful run should return a dict containing endpoint_id and strategy."""
        findings = {"domain": "travel", "capabilities": ["booking"]}
        mock_asyncio_run.return_value = _make_tool_result(
            success=True,
            content={"findings": findings, "conversation": [], "status": "done"},
        )
        mock_tool_cls.return_value = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # Mock user lookup
        mock_user = MagicMock()
        mock_crud = MagicMock()
        mock_crud.get_user.return_value = mock_user

        with (
            patch("rhesis.backend.tasks.endpoint.explore.crud", mock_crud),
            patch(
                "rhesis.backend.tasks.endpoint.explore.get_user_generation_model",
                return_value="vertex_ai/gemini-2.0-flash",
            ),
        ):
            task, mock_self = _make_task()
            result = task.__wrapped__(
                mock_self,
                endpoint_id="ep-uuid",
                strategy="domain_probing",
            )

        assert result["endpoint_id"] == "ep-uuid"
        assert result["strategy"] == "domain_probing"
        assert "duration_ms" in result

    @patch("rhesis.backend.tasks.endpoint.explore.asyncio.run")
    @patch("rhesis.backend.tasks.endpoint.explore.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    def test_update_state_called(
        self,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
    ):
        """update_state should be called at least twice (start + strategy PROGRESS)."""
        mock_asyncio_run.return_value = _make_tool_result(success=True)
        mock_tool_cls.return_value = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_user = MagicMock()
        mock_crud = MagicMock()
        mock_crud.get_user.return_value = mock_user

        with (
            patch("rhesis.backend.tasks.endpoint.explore.crud", mock_crud),
            patch(
                "rhesis.backend.tasks.endpoint.explore.get_user_generation_model",
                return_value="vertex_ai/gemini-2.0-flash",
            ),
        ):
            task, mock_self = _make_task()
            task.__wrapped__(mock_self, endpoint_id="ep-uuid", strategy="capability_mapping")

        assert mock_self.update_state.call_count >= 2


# ---------------------------------------------------------------------------
# Failure path
# ---------------------------------------------------------------------------


class TestRunExplorationTaskFailure:
    @patch("rhesis.backend.tasks.endpoint.explore.asyncio.run")
    @patch("rhesis.backend.tasks.endpoint.explore.ExploreEndpointTool")
    @patch("rhesis.backend.tasks.endpoint.explore.make_target_factory")
    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    def test_raises_on_tool_failure(
        self,
        mock_db_ctx,
        mock_make_factory,
        mock_tool_cls,
        mock_asyncio_run,
    ):
        """When ExploreEndpointTool reports failure, task should raise RuntimeError."""
        mock_asyncio_run.return_value = _make_tool_result(
            success=False, error="Endpoint unreachable"
        )
        mock_tool_cls.return_value = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_user = MagicMock()
        mock_crud = MagicMock()
        mock_crud.get_user.return_value = mock_user

        with (
            patch("rhesis.backend.tasks.endpoint.explore.crud", mock_crud),
            patch(
                "rhesis.backend.tasks.endpoint.explore.get_user_generation_model",
                return_value="vertex_ai/gemini-2.0-flash",
            ),
        ):
            task, mock_self = _make_task()
            with pytest.raises(RuntimeError, match="Endpoint unreachable"):
                task.__wrapped__(mock_self, endpoint_id="ep-uuid", strategy="domain_probing")

    @patch("rhesis.backend.tasks.endpoint.explore.get_db_with_tenant_variables")
    def test_raises_when_user_not_found(self, mock_db_ctx):
        """Task should raise when the user cannot be resolved."""
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_crud = MagicMock()
        mock_crud.get_user.return_value = None  # user not found

        with patch("rhesis.backend.tasks.endpoint.explore.crud", mock_crud):
            task, mock_self = _make_task()
            with pytest.raises(RuntimeError, match="User .* not found"):
                task.__wrapped__(mock_self, endpoint_id="ep-uuid", strategy="domain_probing")


# ---------------------------------------------------------------------------
# make_target_factory
# ---------------------------------------------------------------------------


class TestMakeTargetFactory:
    def test_factory_creates_backend_endpoint_target(self):
        """make_target_factory should return a callable that creates BackendEndpointTarget."""
        from rhesis.backend.tasks.endpoint.target import make_target_factory
        from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget

        mock_db = MagicMock()
        factory = make_target_factory(org_id="org-1", user_id="user-1", db=mock_db)
        assert callable(factory)

        with patch.object(BackendEndpointTarget, "__init__", return_value=None) as mock_init:
            target = factory("ep-uuid")
            mock_init.assert_called_once_with(
                db=mock_db,
                endpoint_id="ep-uuid",
                organization_id="org-1",
                user_id="user-1",
            )

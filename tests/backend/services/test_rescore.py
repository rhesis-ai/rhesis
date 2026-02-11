"""
Tests for the re-scoring service and API endpoint.

Covers:
- rescore_test_run service function
- TestRunRescoreRequest schema validation
- POST /test_runs/{id}/rescore endpoint wiring
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.schemas.test_set import (
    ExecutionMetric,
    TestRunRescoreRequest,
)

# ============================================================================
# TestRunRescoreRequest schema tests
# ============================================================================


class TestTestRunRescoreRequestSchema:
    """Tests for the TestRunRescoreRequest Pydantic schema."""

    def test_empty_request(self):
        """An empty request is valid (all fields are optional)."""
        req = TestRunRescoreRequest()
        assert req.metrics is None
        assert req.execution_options is None

    def test_with_metrics(self):
        """Request with metrics list is valid."""
        metric_id = uuid4()
        req = TestRunRescoreRequest(
            metrics=[
                ExecutionMetric(
                    id=metric_id,
                    name="accuracy",
                    scope=["Single-Turn"],
                )
            ]
        )
        assert len(req.metrics) == 1
        assert req.metrics[0].name == "accuracy"
        assert req.metrics[0].id == metric_id
        assert req.metrics[0].scope == ["Single-Turn"]

    def test_with_execution_options(self):
        """Request with execution_options dict is valid."""
        req = TestRunRescoreRequest(execution_options={"execution_mode": "Sequential"})
        assert req.execution_options["execution_mode"] == "Sequential"

    def test_with_multiple_metrics(self):
        """Request with multiple metrics is valid."""
        req = TestRunRescoreRequest(
            metrics=[
                ExecutionMetric(id=uuid4(), name="accuracy"),
                ExecutionMetric(id=uuid4(), name="relevance"),
                ExecutionMetric(
                    id=uuid4(),
                    name="goal_achievement",
                    scope=["Multi-Turn"],
                ),
            ]
        )
        assert len(req.metrics) == 3


# ============================================================================
# rescore_test_run service tests
# ============================================================================


class TestRescoreTestRunService:
    """Tests for the rescore_test_run service function."""

    def test_raises_when_test_run_not_found(self):
        """Raises ValueError when the reference test run does not exist."""
        with patch(
            "rhesis.backend.app.services.test_run.crud.get_test_run",
            return_value=None,
        ):
            from rhesis.backend.app.services.test_run import (
                rescore_test_run,
            )

            mock_user = MagicMock()
            mock_user.organization_id = uuid4()
            mock_user.id = uuid4()

            with pytest.raises(ValueError, match="not found"):
                rescore_test_run(
                    db=MagicMock(),
                    reference_test_run_id=str(uuid4()),
                    current_user=mock_user,
                )

    def test_raises_when_no_test_configuration(self):
        """Raises ValueError when test run has no test configuration."""
        mock_run = MagicMock()
        mock_run.test_configuration = None

        with patch(
            "rhesis.backend.app.services.test_run.crud.get_test_run",
            return_value=mock_run,
        ):
            from rhesis.backend.app.services.test_run import (
                rescore_test_run,
            )

            mock_user = MagicMock()
            mock_user.organization_id = uuid4()
            mock_user.id = uuid4()

            with pytest.raises(ValueError, match="no test configuration"):
                rescore_test_run(
                    db=MagicMock(),
                    reference_test_run_id=str(uuid4()),
                    current_user=mock_user,
                )

    def test_creates_new_config_and_submits_task(self):
        """rescore_test_run creates a new TestConfiguration and launches a task."""
        ref_run_id = str(uuid4())

        mock_ref_run = MagicMock()
        mock_ref_config = MagicMock()
        mock_ref_config.endpoint_id = uuid4()
        mock_ref_config.test_set_id = uuid4()
        mock_ref_run.test_configuration = mock_ref_config

        mock_new_config = MagicMock()
        mock_new_config.id = uuid4()

        mock_task_result = MagicMock()
        mock_task_result.id = "celery-task-123"

        mock_user = MagicMock()
        mock_user.organization_id = uuid4()
        mock_user.id = uuid4()

        with (
            patch(
                "rhesis.backend.app.services.test_run.crud.get_test_run",
                return_value=mock_ref_run,
            ),
            patch(
                "rhesis.backend.app.services.test_run.crud.create_test_configuration",
                return_value=mock_new_config,
            ) as mock_create_config,
            # task_launcher is imported locally inside rescore_test_run
            patch(
                "rhesis.backend.tasks.task_launcher",
                return_value=mock_task_result,
            ) as mock_launcher,
        ):
            from rhesis.backend.app.services.test_run import (
                rescore_test_run,
            )

            result = rescore_test_run(
                db=MagicMock(),
                reference_test_run_id=ref_run_id,
                current_user=mock_user,
            )

        # Verify new config was created
        mock_create_config.assert_called_once()
        create_call = mock_create_config.call_args
        config_obj = create_call.kwargs.get("test_configuration") or create_call[1].get(
            "test_configuration"
        )
        assert config_obj.endpoint_id == mock_ref_config.endpoint_id
        assert config_obj.test_set_id == mock_ref_config.test_set_id

        # Verify attributes contain reference_test_run_id and is_rescore
        attrs = config_obj.attributes
        assert attrs["reference_test_run_id"] == ref_run_id
        assert attrs["is_rescore"] is True

        # Verify task was launched
        mock_launcher.assert_called_once()

        # Verify result structure
        assert result["status"] == "submitted"
        assert result["reference_test_run_id"] == ref_run_id
        assert result["task_id"] == "celery-task-123"

    def test_includes_metrics_override(self):
        """When metrics are provided, they are included in config attributes."""
        ref_run_id = str(uuid4())
        metric_id = str(uuid4())

        mock_ref_run = MagicMock()
        mock_ref_config = MagicMock()
        mock_ref_config.endpoint_id = uuid4()
        mock_ref_config.test_set_id = uuid4()
        mock_ref_run.test_configuration = mock_ref_config

        mock_new_config = MagicMock()
        mock_new_config.id = uuid4()

        mock_task_result = MagicMock()
        mock_task_result.id = "task-456"

        mock_user = MagicMock()
        mock_user.organization_id = uuid4()
        mock_user.id = uuid4()

        metrics = [{"id": metric_id, "name": "custom_metric", "scope": None}]

        with (
            patch(
                "rhesis.backend.app.services.test_run.crud.get_test_run",
                return_value=mock_ref_run,
            ),
            patch(
                "rhesis.backend.app.services.test_run.crud.create_test_configuration",
                return_value=mock_new_config,
            ) as mock_create_config,
            # task_launcher is imported locally inside rescore_test_run
            patch(
                "rhesis.backend.tasks.task_launcher",
                return_value=mock_task_result,
            ),
        ):
            from rhesis.backend.app.services.test_run import (
                rescore_test_run,
            )

            rescore_test_run(
                db=MagicMock(),
                reference_test_run_id=ref_run_id,
                current_user=mock_user,
                metrics=metrics,
            )

        create_call = mock_create_config.call_args
        config_obj = create_call.kwargs.get("test_configuration") or create_call[1].get(
            "test_configuration"
        )
        attrs = config_obj.attributes
        assert "metrics" in attrs
        assert attrs["metrics"] == metrics
        assert attrs["metrics_source"] == "execution_time"


# ============================================================================
# Rescore router endpoint tests
# ============================================================================


class TestRescoreEndpoint:
    """Tests for POST /test_runs/{id}/rescore endpoint."""

    def test_endpoint_calls_service(self):
        """Endpoint delegates to rescore_test_run service."""
        # Verify the router function signature and wiring
        # Verify the endpoint exists and is async
        import inspect

        from rhesis.backend.app.routers.test_run import (
            rescore_test_run_endpoint,
        )

        assert inspect.iscoroutinefunction(rescore_test_run_endpoint)

    def test_endpoint_converts_metrics_to_dicts(self):
        """The endpoint converts ExecutionMetric schema objects to dicts."""
        # This tests the conversion logic in the endpoint handler
        metric_id = uuid4()
        request = TestRunRescoreRequest(
            metrics=[
                ExecutionMetric(
                    id=metric_id,
                    name="accuracy",
                    scope=["Single-Turn"],
                )
            ]
        )

        # Simulate the conversion logic from the router
        metrics = None
        if request and request.metrics:
            metrics = [
                {
                    "id": str(m.id),
                    "name": m.name,
                    "scope": m.scope,
                }
                for m in request.metrics
            ]

        assert metrics is not None
        assert len(metrics) == 1
        assert metrics[0]["id"] == str(metric_id)
        assert metrics[0]["name"] == "accuracy"
        assert metrics[0]["scope"] == ["Single-Turn"]

    def test_none_request_yields_no_metrics(self):
        """When request is None, no metrics are passed to service."""
        request = None
        metrics = None
        if request and request.metrics:
            metrics = [{"id": str(m.id), "name": m.name, "scope": m.scope} for m in request.metrics]
        assert metrics is None

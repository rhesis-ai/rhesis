"""Preflight metric loading: SDK metrics go through the connector, failures are named (#2849)."""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.schemas.preflight import PreflightCheckStatus
from rhesis.backend.app.services.connector import rpc_client
from rhesis.backend.app.services.preflight import CHECK_EVALUATION_MODEL, CHECK_EXECUTION_MODEL
from rhesis.backend.app.services.preflight.checks import _validate_metrics_loadable
from rhesis.backend.app.services.preflight.utils import PreflightDbGate
from rhesis.sdk.metrics import MetricConfig

RESOLVE_MODEL = "rhesis.backend.app.utils.user_model_utils.resolve_model"
VALIDATE_CONFIGS = "rhesis.backend.metrics.metric_config.validate_metric_configs"
ROUTE_STATUS = "rhesis.backend.app.services.preflight.checks.sdk_metric_route_status"


def _sdk_config(name: str = "my_sdk_metric") -> MetricConfig:
    return MetricConfig(class_name=name, backend="sdk", name=name, threshold=0.5)


def _local_config(class_name: str, name: str) -> MetricConfig:
    return MetricConfig(class_name=class_name, backend="rhesis", name=name, threshold=0.5)


def _endpoint(project_id="proj-1", environment="Development"):
    endpoint = MagicMock()
    endpoint.project_id = project_id
    endpoint.environment = environment
    return endpoint


async def _validate(configs, user=None, endpoint=None):
    user = user or MagicMock(organization_id=uuid4())
    with patch(VALIDATE_CONFIGS, return_value=(configs, {})):
        rows = [SimpleNamespace(name=c.name) for c in configs]
        return await _validate_metrics_loadable(
            PreflightDbGate(MagicMock()), user, rows, endpoint=endpoint
        )


class TestSdkMetricsInPreflight:
    @pytest.mark.asyncio
    async def test_registered_sdk_metric_passes(self):
        """Before the fix this went through MetricFactory.create("sdk", ...) and came
        back as "1 of 1 metric(s) failed to load"."""
        user = MagicMock(organization_id=uuid4())
        with (
            patch(RESOLVE_MODEL, return_value=MagicMock()),
            patch(ROUTE_STATUS, new_callable=AsyncMock, return_value="registered") as status,
        ):
            result = await _validate([_sdk_config()], user=user, endpoint=_endpoint())

        assert result.status == PreflightCheckStatus.PASSED, result
        status.assert_awaited_once_with(
            str(user.organization_id), "my_sdk_metric", "proj-1", "Development"
        )

    @pytest.mark.asyncio
    async def test_unregistered_sdk_metric_fails_naming_the_metric(self):
        with patch(ROUTE_STATUS, new_callable=AsyncMock, return_value="not_registered"):
            result = await _validate([_sdk_config("tone_check")], endpoint=_endpoint())

        assert result.status == PreflightCheckStatus.FAILED
        assert "tone_check" in result.detail
        assert "not registered" in result.detail

    @pytest.mark.asyncio
    async def test_sdk_metric_without_connector_fails_naming_the_metric(self):
        with patch(ROUTE_STATUS, new_callable=AsyncMock, return_value="no_connector"):
            result = await _validate([_sdk_config("tone_check")])

        assert result.status == PreflightCheckStatus.FAILED
        assert "tone_check" in result.detail

    @pytest.mark.asyncio
    async def test_redis_down_is_a_warning(self):
        with patch(
            ROUTE_STATUS,
            new_callable=AsyncMock,
            side_effect=RuntimeError("Redis connection failed"),
        ):
            result = await _validate([_sdk_config()], endpoint=_endpoint())

        assert result.status == PreflightCheckStatus.WARNING
        assert "Redis connection failed" in result.detail

    @pytest.mark.asyncio
    async def test_all_sdk_test_set_does_not_build_the_evaluation_model(self):
        resolve = MagicMock()
        with (
            patch(RESOLVE_MODEL, resolve),
            patch(ROUTE_STATUS, new_callable=AsyncMock, return_value="registered"),
        ):
            result = await _validate([_sdk_config("a"), _sdk_config("b")])

        assert result.status == PreflightCheckStatus.PASSED
        resolve.assert_not_called()


class TestLocalMetricFailuresAreNamed:
    @pytest.mark.asyncio
    async def test_local_metric_that_fails_to_load_is_named_with_reason(self):
        configs = [_local_config("NoSuchMetric", "My broken metric"), _sdk_config()]
        with (
            patch(RESOLVE_MODEL, return_value=MagicMock()),
            patch(ROUTE_STATUS, new_callable=AsyncMock, return_value="registered"),
        ):
            result = await _validate(configs)

        assert result.status == PreflightCheckStatus.WARNING
        assert result.message == "1 of 2 metric(s) failed to load"
        assert "My broken metric" in result.detail
        assert "NoSuchMetric" in result.detail


class TestSdkMetricRouteStatus:
    """The lookup reads the same Redis keys the connector writes and execution reads."""

    @pytest.fixture
    def redis(self):
        redis = MagicMock()
        redis.exists = AsyncMock(return_value=0)
        client = MagicMock(_redis=redis)
        with patch.object(rpc_client, "get_rpc_client", AsyncMock(return_value=client)):
            yield redis

    @pytest.mark.asyncio
    async def test_metric_key_means_registered(self, redis):
        redis.exists.side_effect = lambda key: int(key == "ws:metric:org-1:tone")
        status = await rpc_client.sdk_metric_route_status("org-1", "tone", "p", "Dev")
        assert status == rpc_client.METRIC_ROUTE_REGISTERED

    @pytest.mark.asyncio
    async def test_project_route_without_metric_means_not_registered(self, redis):
        redis.exists.side_effect = lambda key: int(key == "ws:routing:p:dev")
        status = await rpc_client.sdk_metric_route_status("org-1", "tone", "p", "Dev")
        assert status == rpc_client.METRIC_ROUTE_NOT_REGISTERED

    @pytest.mark.asyncio
    async def test_nothing_means_no_connector(self, redis):
        status = await rpc_client.sdk_metric_route_status("org-1", "tone")
        assert status == rpc_client.METRIC_ROUTE_NO_CONNECTOR


class TestModelChecksFollowRunNeeds:
    """The shared model checks use the execute route's rule (``run_models.model_needs``)."""

    ORCH = "rhesis.backend.app.services.preflight.orchestrator"
    OTHER_CHECKS = (
        "check_test_set_not_empty",
        "check_requirement_metric_coverage",
        "check_metric_compatibility",
        "_connectivity_branch",
    )

    async def _run(self, stack, backends, is_multi_turn=False, scoring_target="fresh"):
        from rhesis.backend.app.services.preflight.orchestrator import (
            run_preflight_checks_multi,
        )

        passed = MagicMock(status=PreflightCheckStatus.PASSED)
        stack.enter_context(patch(f"{self.ORCH}.get_item_detail", return_value=_endpoint()))
        for name in self.OTHER_CHECKS:
            stack.enter_context(
                patch(f"{self.ORCH}.{name}", new_callable=AsyncMock, return_value=passed)
            )
        if isinstance(backends, Exception):
            stack.enter_context(patch(f"{self.ORCH}._resolve_check_metrics", side_effect=backends))
        else:
            stack.enter_context(patch(f"{self.ORCH}.metric_backends", return_value=backends))
        return await run_preflight_checks_multi(
            db=MagicMock(),
            user=MagicMock(organization_id=uuid4()),
            test_sets=[(uuid4(), "Test Set", is_multi_turn)],
            endpoint_id=uuid4(),
            scoring_target=scoring_target,
            publish=False,
        )

    def _patch_model_checks(self, stack):
        passed = MagicMock(status=PreflightCheckStatus.PASSED)
        evaluation = stack.enter_context(
            patch(
                f"{self.ORCH}.check_evaluation_model", new_callable=AsyncMock, return_value=passed
            )
        )
        execution = stack.enter_context(
            patch(f"{self.ORCH}.check_execution_model", new_callable=AsyncMock, return_value=passed)
        )
        return evaluation, execution

    @staticmethod
    def _status(results, check_id):
        return next(r.status for r in results if getattr(r, "check_id", None) == check_id)

    @pytest.mark.asyncio
    async def test_all_sdk_single_turn_skips_the_evaluation_model(self):

        sdk_metric = SimpleNamespace(
            name="tone_check", class_name="tone_check", metric_scope=["Single-Turn"]
        )
        resolve_model = MagicMock()
        with ExitStack() as stack:
            resolve = stack.enter_context(
                patch(f"{self.ORCH}._resolve_check_metrics", return_value=[sdk_metric])
            )
            stack.enter_context(patch(RESOLVE_MODEL, resolve_model))
            stack.enter_context(patch(VALIDATE_CONFIGS, return_value=([_sdk_config()], {})))
            stack.enter_context(
                patch(ROUTE_STATUS, new_callable=AsyncMock, return_value="registered")
            )
            results = await self._run(stack, ["sdk"])

        assert self._status(results, CHECK_EVALUATION_MODEL) == PreflightCheckStatus.SKIPPED
        resolve_model.assert_not_called()
        # Resolved once up front and reused by the metric check.
        resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixed_set_runs_the_evaluation_check(self):

        with ExitStack() as stack:
            evaluation, _ = self._patch_model_checks(stack)
            stack.enter_context(
                patch(
                    f"{self.ORCH}.check_metric_functionality",
                    new_callable=AsyncMock,
                    return_value=MagicMock(status=PreflightCheckStatus.PASSED),
                )
            )
            await self._run(stack, ["rhesis", "sdk"])

        evaluation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multi_turn_rescore_skips_the_execution_model(self):

        with ExitStack() as stack:
            evaluation, execution = self._patch_model_checks(stack)
            stack.enter_context(
                patch(
                    f"{self.ORCH}.check_metric_functionality",
                    new_callable=AsyncMock,
                    return_value=MagicMock(status=PreflightCheckStatus.PASSED),
                )
            )
            results = await self._run(stack, ["sdk"], is_multi_turn=True, scoring_target="reuse")

        execution.assert_not_awaited()
        assert self._status(results, CHECK_EXECUTION_MODEL) == PreflightCheckStatus.SKIPPED
        # Multi-turn scoring still needs the evaluation model.
        evaluation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unresolvable_metrics_fall_back_to_both_checks(self):

        with ExitStack() as stack:
            evaluation, execution = self._patch_model_checks(stack)
            stack.enter_context(
                patch(
                    f"{self.ORCH}.check_metric_functionality",
                    new_callable=AsyncMock,
                    return_value=MagicMock(status=PreflightCheckStatus.PASSED),
                )
            )
            await self._run(stack, RuntimeError("db gone"), is_multi_turn=True)

        evaluation.assert_awaited_once()
        execution.assert_awaited_once()

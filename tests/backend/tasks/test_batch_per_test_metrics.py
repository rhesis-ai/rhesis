"""
Tests for per-test metric resolution in batch execution.

Covers the fix for the bug where batch execution resolved metrics from only
tests[0] and applied them to all tests, ignoring per-test behavior metrics.

Scenarios:
- Behavior-mapped metrics (Priority 3) are resolved per-test
- Test-set metrics (Priority 2) remain shared across all tests
- Execution-time metrics (Priority 1) remain shared across all tests
- ExecutionContext.get_metric_configs_for_test returns correct configs
- Batch evaluation uses per-test configs
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.tasks.execution.batch.context import ExecutionContext

# ============================================================================
# Helpers
# ============================================================================


def _make_metric_config(name: str, class_name: str) -> MagicMock:
    mc = MagicMock()
    mc.name = name
    mc.class_name = class_name
    return mc


def _make_execution_context(**overrides) -> ExecutionContext:
    """Build a minimal ExecutionContext with sensible defaults."""
    defaults = dict(
        test_config=MagicMock(),
        test_run=MagicMock(),
        test_set=MagicMock(),
        endpoint=MagicMock(),
        organization_id="org-1",
        user_id="user-1",
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


# ============================================================================
# ExecutionContext.get_metric_configs_for_test
# ============================================================================


class TestGetMetricConfigsForTest:
    """Tests for the per-test metric lookup method on ExecutionContext."""

    def test_returns_shared_when_no_per_test(self):
        """Falls back to shared metric_configs when per_test_metric_configs is empty."""
        shared = [_make_metric_config("Shared", "SharedJudge")]
        ctx = _make_execution_context(metric_configs=shared)

        assert ctx.get_metric_configs_for_test("any-test-id") == shared

    def test_returns_per_test_configs(self):
        """Returns per-test configs when available."""
        mc_a = [_make_metric_config("MetricA", "JudgeA")]
        mc_b = [_make_metric_config("MetricB", "JudgeB")]
        ctx = _make_execution_context(
            per_test_metric_configs={"test-1": mc_a, "test-2": mc_b},
        )

        assert ctx.get_metric_configs_for_test("test-1") == mc_a
        assert ctx.get_metric_configs_for_test("test-2") == mc_b

    def test_returns_empty_for_unknown_test(self):
        """Returns empty list for a test ID not in per_test_metric_configs."""
        mc_a = [_make_metric_config("MetricA", "JudgeA")]
        ctx = _make_execution_context(
            per_test_metric_configs={"test-1": mc_a},
        )

        assert ctx.get_metric_configs_for_test("unknown-id") == []

    def test_per_test_takes_precedence_over_shared(self):
        """per_test_metric_configs is preferred when populated, even if
        metric_configs is also set."""
        shared = [_make_metric_config("Shared", "SharedJudge")]
        per_test = [_make_metric_config("PerTest", "PerTestJudge")]
        ctx = _make_execution_context(
            metric_configs=shared,
            per_test_metric_configs={"test-1": per_test},
        )

        assert ctx.get_metric_configs_for_test("test-1") == per_test


class TestHasMetrics:
    """Tests for the has_metrics property."""

    def test_false_when_empty(self):
        ctx = _make_execution_context()
        assert ctx.has_metrics is False

    def test_true_with_shared(self):
        ctx = _make_execution_context(
            metric_configs=[_make_metric_config("M", "J")]
        )
        assert ctx.has_metrics is True

    def test_true_with_per_test(self):
        ctx = _make_execution_context(
            per_test_metric_configs={"t1": [_make_metric_config("M", "J")]}
        )
        assert ctx.has_metrics is True


# ============================================================================
# prefetch_execution_context: per-test vs shared metrics
# ============================================================================


class TestPrefetchMetricResolution:
    """Tests that prefetch_execution_context resolves metrics correctly
    based on the active priority level."""

    def _make_test(self, test_id, behavior_name, metric_name, metric_class):
        """Create a mock Test with a behavior and one metric."""
        metric = MagicMock()
        metric.name = metric_name
        metric.class_name = metric_class
        metric.id = uuid4()
        metric.metric_scope = ["Single-Turn"]

        behavior = MagicMock()
        behavior.name = behavior_name
        behavior.metrics = [metric]

        test = MagicMock()
        test.id = uuid4() if test_id is None else test_id
        test.behavior = behavior
        test.behavior_id = uuid4()
        test.project_id = None
        test.prompt = MagicMock()
        test.prompt.content = "test prompt"
        test.prompt.expected_response = "expected"
        test.test_type = None
        test.test_configuration = None
        test.test_metadata = None
        return test, metric

    @patch("rhesis.backend.metrics.metric_config.metric_model_to_config")
    @patch(
        "rhesis.backend.tasks.execution.executors.data.get_test_metrics"
    )
    def test_behavior_metrics_resolved_per_test(
        self, mock_get_metrics, mock_to_config
    ):
        """When using behavior metrics (P3), each test gets its own configs."""
        test_1, metric_1 = self._make_test(
            "t1", "Behavior A", "Metric A", "JudgeA"
        )
        test_2, metric_2 = self._make_test(
            "t2", "Behavior B", "Metric B", "JudgeB"
        )

        # get_test_metrics returns different metrics per test; the sample-test
        # call passes return_source=True and expects a (metrics, source) tuple.
        def side_effect(test, *args, **kwargs):
            metrics = {str(test_1.id): [metric_1], str(test_2.id): [metric_2]}[
                str(test.id)
            ]
            if kwargs.get("return_source"):
                return metrics, "behavior"
            return metrics

        mock_get_metrics.side_effect = side_effect

        # metric_model_to_config returns a mock config with the name
        def to_config(m):
            cfg = MagicMock()
            cfg.name = m.name
            cfg.class_name = m.class_name
            return cfg

        mock_to_config.side_effect = to_config

        # Test set with NO direct metrics (triggers P3)
        test_set = MagicMock()
        test_set.metrics = []
        test_set.id = uuid4()

        test_config = MagicMock()
        test_config.attributes = {}
        test_config.organization_id = uuid4()
        test_config.user_id = uuid4()
        test_config.project_id = None
        test_config.test_set_id = test_set.id
        test_config.endpoint_id = uuid4()

        test_run = MagicMock()
        test_run.id = uuid4()

        endpoint = MagicMock()
        endpoint.id = test_config.endpoint_id
        endpoint.project_id = None
        endpoint.environment = None

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = endpoint

        with (
            patch(
                "rhesis.backend.app.database.bind_scope_to_session"
            ),
            patch(
                "rhesis.backend.app.services.test_set.get_test_set",
                return_value=test_set,
            ),
            patch(
                "rhesis.backend.app.services.invokers.auth.manager"
                ".AuthenticationManager"
            ),
            patch(
                "rhesis.backend.app.config.settings.get_model_settings"
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.data"
                ".get_test_and_prompt",
                side_effect=lambda s, tid, org: (
                    test_1 if tid == str(test_1.id) else test_2,
                    "prompt",
                    "expected",
                ),
            ),
        ):
            from rhesis.backend.tasks.execution.batch.context import (
                prefetch_execution_context,
            )

            ctx = prefetch_execution_context(
                session, test_config, test_run, [test_1, test_2]
            )

        # Shared should be empty; per-test should have entries
        assert ctx.metric_configs == []
        assert str(test_1.id) in ctx.per_test_metric_configs
        assert str(test_2.id) in ctx.per_test_metric_configs

        configs_1 = ctx.per_test_metric_configs[str(test_1.id)]
        configs_2 = ctx.per_test_metric_configs[str(test_2.id)]
        assert len(configs_1) == 1
        assert len(configs_2) == 1
        assert configs_1[0].class_name == "JudgeA"
        assert configs_2[0].class_name == "JudgeB"

    @patch("rhesis.backend.metrics.metric_config.metric_model_to_config")
    @patch(
        "rhesis.backend.tasks.execution.executors.data.get_test_metrics"
    )
    def test_test_set_metrics_shared(self, mock_get_metrics, mock_to_config):
        """When using test_set metrics (P2), all tests share the same configs."""
        test_1, _ = self._make_test("t1", "Behavior A", "Metric A", "JudgeA")
        test_2, _ = self._make_test("t2", "Behavior B", "Metric B", "JudgeB")

        shared_metric = MagicMock()
        shared_metric.name = "Shared Metric"
        shared_metric.class_name = "SharedJudge"
        shared_metric.id = uuid4()

        # get_test_metrics returns the shared metric (from test_set, P2); the
        # sample-test call passes return_source=True and expects a tuple back.
        mock_get_metrics.return_value = ([shared_metric], "test_set")

        def to_config(m):
            cfg = MagicMock()
            cfg.name = m.name
            cfg.class_name = m.class_name
            return cfg

        mock_to_config.side_effect = to_config

        # Test set WITH direct metrics (triggers P2)
        test_set = MagicMock()
        test_set.metrics = [shared_metric]
        test_set.id = uuid4()

        test_config = MagicMock()
        test_config.attributes = {}
        test_config.organization_id = uuid4()
        test_config.user_id = uuid4()
        test_config.project_id = None
        test_config.test_set_id = test_set.id
        test_config.endpoint_id = uuid4()

        test_run = MagicMock()
        test_run.id = uuid4()

        endpoint = MagicMock()
        endpoint.id = test_config.endpoint_id
        endpoint.project_id = None
        endpoint.environment = None

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = endpoint

        with (
            patch(
                "rhesis.backend.app.database.bind_scope_to_session"
            ),
            patch(
                "rhesis.backend.app.services.test_set.get_test_set",
                return_value=test_set,
            ),
            patch(
                "rhesis.backend.app.services.invokers.auth.manager"
                ".AuthenticationManager"
            ),
            patch(
                "rhesis.backend.app.config.settings.get_model_settings"
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.data"
                ".get_test_and_prompt",
                side_effect=lambda s, tid, org: (
                    test_1 if tid == str(test_1.id) else test_2,
                    "prompt",
                    "expected",
                ),
            ),
        ):
            from rhesis.backend.tasks.execution.batch.context import (
                prefetch_execution_context,
            )

            ctx = prefetch_execution_context(
                session, test_config, test_run, [test_1, test_2]
            )

        # Shared should be populated; per-test should be empty
        assert len(ctx.metric_configs) == 1
        assert ctx.metric_configs[0].class_name == "SharedJudge"
        assert ctx.per_test_metric_configs == {}

        # Both tests should get the same shared configs
        assert ctx.get_metric_configs_for_test(str(test_1.id)) == ctx.metric_configs
        assert ctx.get_metric_configs_for_test(str(test_2.id)) == ctx.metric_configs


class TestPrefetchFallthroughToPerTest:
    """Regression test: a *configured* P1 (execution-time) override that
    resolves to zero valid metrics must fall through to per-test P3
    resolution, not be treated as shared just because
    test_configuration.attributes['metrics'] is merely present."""

    def _make_test(self, test_id, behavior_name, metric_name, metric_class):
        metric = MagicMock()
        metric.name = metric_name
        metric.class_name = metric_class
        metric.id = uuid4()
        metric.metric_scope = ["Single-Turn"]

        behavior = MagicMock()
        behavior.name = behavior_name
        behavior.metrics = [metric]

        test = MagicMock()
        test.id = uuid4() if test_id is None else test_id
        test.behavior = behavior
        test.behavior_id = uuid4()
        test.project_id = None
        test.prompt = MagicMock()
        test.prompt.content = "test prompt"
        test.prompt.expected_response = "expected"
        test.test_type = None
        test.test_configuration = None
        test.test_metadata = None
        return test, metric

    @patch("rhesis.backend.metrics.metric_config.metric_model_to_config")
    @patch("rhesis.backend.tasks.execution.executors.data.get_test_metrics")
    def test_configured_but_invalid_execution_time_metrics_falls_back_per_test(
        self, mock_get_metrics, mock_to_config
    ):
        test_1, metric_1 = self._make_test("t1", "Behavior A", "Metric A", "JudgeA")
        test_2, metric_2 = self._make_test("t2", "Behavior B", "Metric B", "JudgeB")

        # get_test_metrics reports that P1 (execution_time) was configured but
        # resolved to nothing valid, so it fell through to P3 (behavior) —
        # which differs per test.
        def side_effect(test, *args, **kwargs):
            metrics = {str(test_1.id): [metric_1], str(test_2.id): [metric_2]}[
                str(test.id)
            ]
            if kwargs.get("return_source"):
                return metrics, "behavior"
            return metrics

        mock_get_metrics.side_effect = side_effect

        def to_config(m):
            cfg = MagicMock()
            cfg.name = m.name
            cfg.class_name = m.class_name
            return cfg

        mock_to_config.side_effect = to_config

        test_set = MagicMock()
        test_set.metrics = []
        test_set.id = uuid4()

        test_config = MagicMock()
        # P1 is *configured* (non-empty) but, per the mocked source above,
        # resolves to nothing valid and falls through to P3 internally.
        test_config.attributes = {"metrics": [{"id": str(uuid4())}]}
        test_config.organization_id = uuid4()
        test_config.user_id = uuid4()
        test_config.project_id = None
        test_config.test_set_id = test_set.id
        test_config.endpoint_id = uuid4()

        test_run = MagicMock()
        test_run.id = uuid4()

        endpoint = MagicMock()
        endpoint.id = test_config.endpoint_id
        endpoint.project_id = None
        endpoint.environment = None

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = endpoint

        with (
            patch("rhesis.backend.app.database.bind_scope_to_session"),
            patch(
                "rhesis.backend.app.services.test_set.get_test_set",
                return_value=test_set,
            ),
            patch(
                "rhesis.backend.app.services.invokers.auth.manager"
                ".AuthenticationManager"
            ),
            patch("rhesis.backend.app.config.settings.get_model_settings"),
            patch(
                "rhesis.backend.tasks.execution.executors.data"
                ".get_test_and_prompt",
                side_effect=lambda s, tid, org: (
                    test_1 if tid == str(test_1.id) else test_2,
                    "prompt",
                    "expected",
                ),
            ),
        ):
            from rhesis.backend.tasks.execution.batch.context import (
                prefetch_execution_context,
            )

            ctx = prefetch_execution_context(
                session, test_config, test_run, [test_1, test_2]
            )

        # Even though P1 config was present, it didn't actually win — the
        # per-test path must be used, not a single shared resolution from
        # tests[0].
        assert ctx.metric_configs == []
        assert str(test_1.id) in ctx.per_test_metric_configs
        assert str(test_2.id) in ctx.per_test_metric_configs

        configs_1 = ctx.per_test_metric_configs[str(test_1.id)]
        configs_2 = ctx.per_test_metric_configs[str(test_2.id)]
        assert len(configs_1) == 1
        assert len(configs_2) == 1
        assert configs_1[0].class_name == "JudgeA"
        assert configs_2[0].class_name == "JudgeB"


# ============================================================================
# Batch evaluation uses per-test configs
# ============================================================================


class TestBatchEvaluationPerTestMetrics:
    """Tests that batch evaluation passes the correct per-test metrics."""

    @pytest.mark.asyncio
    async def test_evaluate_uses_per_test_configs(self):
        """evaluate_metrics passes per-test configs to the evaluator, not shared."""
        mc_a = _make_metric_config("MetricA", "JudgeA")
        mc_b = _make_metric_config("MetricB", "JudgeB")

        ctx = _make_execution_context(
            per_test_metric_configs={
                "test-1": [mc_a],
                "test-2": [mc_b],
            },
        )

        mock_evaluator = MagicMock()
        mock_evaluator.a_evaluate = MagicMock(
            return_value={"MetricA": {"is_successful": True}}
        )
        # Make it awaitable
        import asyncio

        future = asyncio.Future()
        future.set_result({"MetricA": {"is_successful": True}})
        mock_evaluator.a_evaluate.return_value = future

        test = MagicMock()
        test.test_metadata = None

        with (
            patch(
                "rhesis.backend.tasks.execution.response_extractor"
                ".extract_response_with_fallback",
                return_value="response text",
            ),
            patch(
                "rhesis.backend.tasks.execution.response_extractor"
                ".normalize_context_to_list",
                return_value=[],
            ),
            patch(
                "rhesis.backend.tasks.execution.evaluation._is_multi_turn_only",
                return_value=False,
            ),
        ):
            from rhesis.backend.tasks.execution.batch.evaluation import (
                evaluate_metrics,
            )

            await evaluate_metrics(
                ctx=ctx,
                evaluator=mock_evaluator,
                test=test,
                test_id="test-1",
                output={"output": "response text"},
                prompt_content="prompt",
                expected_response="expected",
                is_multi_turn=False,
                penelope_metrics={},
            )

        # The evaluator should have been called with test-1's metric (MetricA),
        # not test-2's (MetricB) or an empty shared list.
        call_kwargs = mock_evaluator.a_evaluate.call_args
        metrics_passed = call_kwargs.kwargs.get("metrics") or call_kwargs[1].get(
            "metrics"
        )
        assert len(metrics_passed) == 1
        assert metrics_passed[0].class_name == "JudgeA"

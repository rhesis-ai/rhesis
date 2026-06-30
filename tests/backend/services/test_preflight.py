"""Tests for preflight check service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus
from rhesis.backend.app.services.preflight import (
    CHECK_BEHAVIOR_METRIC_COVERAGE,
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_EXECUTION_MODEL,
    CHECK_METRIC_COMPATIBILITY,
    CHECK_METRIC_FUNCTIONALITY,
    CHECK_TEST_SET_NOT_EMPTY,
    LABELS,
    compute_summary,
)
from rhesis.backend.app.services.preflight.utils import (
    _apply_test_set_fields,
    _make_composite_key,
    _make_result,
)


class TestConstants:
    def test_all_checks_have_labels(self):
        all_checks = [
            CHECK_ENDPOINT_CONNECTIVITY,
            CHECK_EVALUATION_MODEL,
            CHECK_EXECUTION_MODEL,
            CHECK_BEHAVIOR_METRIC_COVERAGE,
            CHECK_METRIC_COMPATIBILITY,
            CHECK_METRIC_FUNCTIONALITY,
            CHECK_TEST_SET_NOT_EMPTY,
        ]
        for check_id in all_checks:
            assert check_id in LABELS, f"Missing label for {check_id}"
            assert isinstance(LABELS[check_id], str)
            assert len(LABELS[check_id]) > 0


class TestCompositeKey:
    def test_shared_check_no_test_set(self):
        assert _make_composite_key(CHECK_ENDPOINT_CONNECTIVITY) == CHECK_ENDPOINT_CONNECTIVITY

    def test_shared_check_ignores_test_set_id(self):
        ts_id = str(uuid4())
        assert _make_composite_key(CHECK_ENDPOINT_CONNECTIVITY, ts_id) == CHECK_ENDPOINT_CONNECTIVITY

    def test_per_test_set_check_with_id(self):
        ts_id = str(uuid4())
        result = _make_composite_key(CHECK_TEST_SET_NOT_EMPTY, ts_id)
        assert result == f"{CHECK_TEST_SET_NOT_EMPTY}:{ts_id}"

    def test_per_test_set_check_without_id(self):
        assert _make_composite_key(CHECK_TEST_SET_NOT_EMPTY) == CHECK_TEST_SET_NOT_EMPTY


class TestMakeResult:
    def test_basic_result(self):
        result = _make_result(CHECK_ENDPOINT_CONNECTIVITY, PreflightCheckStatus.PASSED)
        assert result.check_id == CHECK_ENDPOINT_CONNECTIVITY
        assert result.label == LABELS[CHECK_ENDPOINT_CONNECTIVITY]
        assert result.status == PreflightCheckStatus.PASSED
        assert result.message is None
        assert result.detail is None

    def test_result_with_message_and_detail(self):
        result = _make_result(
            CHECK_EVALUATION_MODEL,
            PreflightCheckStatus.FAILED,
            "Model not configured",
            "Set up an evaluation model in settings.",
        )
        assert result.status == PreflightCheckStatus.FAILED
        assert result.message == "Model not configured"
        assert result.detail == "Set up an evaluation model in settings."


class TestApplyTestSetFields:
    def test_no_test_set(self):
        result = _make_result(CHECK_TEST_SET_NOT_EMPTY, PreflightCheckStatus.PASSED)
        _apply_test_set_fields(result)
        assert result.test_set_id is None
        assert result.composite_key == CHECK_TEST_SET_NOT_EMPTY

    def test_with_test_set(self):
        ts_id = str(uuid4())
        result = _make_result(CHECK_TEST_SET_NOT_EMPTY, PreflightCheckStatus.PASSED)
        _apply_test_set_fields(result, ts_id, "My Test Set")
        assert result.test_set_id == ts_id
        assert result.test_set_name == "My Test Set"
        assert result.composite_key == f"{CHECK_TEST_SET_NOT_EMPTY}:{ts_id}"


class TestComputeSummary:
    def test_all_passed(self):
        results = [
            _make_result(CHECK_ENDPOINT_CONNECTIVITY, PreflightCheckStatus.PASSED),
            _make_result(CHECK_EVALUATION_MODEL, PreflightCheckStatus.PASSED),
            _make_result(CHECK_TEST_SET_NOT_EMPTY, PreflightCheckStatus.PASSED),
        ]
        summary, passed, failed, warnings, skipped = compute_summary(results)
        assert summary == "passed"
        assert passed == 3
        assert failed == 0
        assert warnings == 0
        assert skipped == 0

    def test_failure_takes_precedence(self):
        results = [
            _make_result(CHECK_ENDPOINT_CONNECTIVITY, PreflightCheckStatus.PASSED),
            _make_result(CHECK_EVALUATION_MODEL, PreflightCheckStatus.FAILED),
            _make_result(CHECK_TEST_SET_NOT_EMPTY, PreflightCheckStatus.WARNING),
        ]
        summary, passed, failed, warnings, skipped = compute_summary(results)
        assert summary == "failed"
        assert passed == 1
        assert failed == 1
        assert warnings == 1

    def test_warning_without_failure(self):
        results = [
            _make_result(CHECK_ENDPOINT_CONNECTIVITY, PreflightCheckStatus.PASSED),
            _make_result(CHECK_BEHAVIOR_METRIC_COVERAGE, PreflightCheckStatus.WARNING),
        ]
        summary, passed, failed, warnings, skipped = compute_summary(results)
        assert summary == "warning"
        assert passed == 1
        assert warnings == 1

    def test_empty_results(self):
        summary, passed, failed, warnings, skipped = compute_summary([])
        assert summary == "passed"
        assert passed == 0

    def test_skipped_counts(self):
        results = [
            _make_result(CHECK_ENDPOINT_CONNECTIVITY, PreflightCheckStatus.SKIPPED),
            _make_result(CHECK_EVALUATION_MODEL, PreflightCheckStatus.PASSED),
        ]
        summary, passed, failed, warnings, skipped = compute_summary(results)
        assert summary == "passed"
        assert skipped == 1
        assert passed == 1


class TestCheckTestSetNotEmpty:
    @pytest.mark.asyncio
    async def test_empty_test_set(self):
        from rhesis.backend.app.services.preflight.checks import check_test_set_not_empty

        ts_id = uuid4()
        db = MagicMock()
        query = db.query.return_value.filter.return_value
        query.count.return_value = 0

        result = await check_test_set_not_empty(db, ts_id, publish=False)
        assert result.status == PreflightCheckStatus.FAILED
        assert "no tests" in result.message.lower()

    @pytest.mark.asyncio
    async def test_nonempty_test_set(self):
        from rhesis.backend.app.services.preflight.checks import check_test_set_not_empty

        ts_id = uuid4()
        db = MagicMock()
        query = db.query.return_value.filter.return_value
        query.count.return_value = 42

        result = await check_test_set_not_empty(db, ts_id, publish=False)
        assert result.status == PreflightCheckStatus.PASSED
        assert "42" in result.message

    @pytest.mark.asyncio
    async def test_db_error(self):
        from rhesis.backend.app.services.preflight.checks import check_test_set_not_empty

        ts_id = uuid4()
        db = MagicMock()
        db.query.side_effect = RuntimeError("connection lost")

        result = await check_test_set_not_empty(db, ts_id, publish=False)
        assert result.status == PreflightCheckStatus.FAILED
        assert "connection lost" in result.detail


class TestCheckEvaluationModel:
    MODEL_UTIL = (
        "rhesis.backend.app.utils.user_model_utils.get_evaluation_model_with_override"
    )

    @pytest.mark.asyncio
    async def test_model_passes(self):
        from rhesis.backend.app.services.preflight.checks import check_evaluation_model

        db = MagicMock()
        user = MagicMock()
        user.organization_id = uuid4()
        user.settings.models.evaluation.model_id = None

        mock_model = MagicMock()

        with (
            patch(self.MODEL_UTIL, return_value=mock_model),
            patch(
                "rhesis.backend.app.services.preflight.utils._verify_model_responds",
                new_callable=AsyncMock,
            ),
            patch(
                "rhesis.backend.app.services.preflight.checks._build_model_detail",
                return_value="OpenAI / gpt-4o",
            ),
        ):
            result = await check_evaluation_model(db, user, publish=False)

        assert result.status == PreflightCheckStatus.PASSED
        assert result.detail == "OpenAI / gpt-4o"

    @pytest.mark.asyncio
    async def test_model_timeout(self):
        from rhesis.backend.app.services.preflight.checks import check_evaluation_model

        db = MagicMock()
        user = MagicMock()
        user.organization_id = uuid4()

        with patch(self.MODEL_UTIL, side_effect=asyncio.TimeoutError()):
            result = await check_evaluation_model(db, user, publish=False)

        assert result.status == PreflightCheckStatus.FAILED
        assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_model_config_error(self):
        from rhesis.backend.app.services.preflight.checks import check_evaluation_model

        db = MagicMock()
        user = MagicMock()
        user.organization_id = uuid4()

        with patch(self.MODEL_UTIL, side_effect=ValueError("No API key configured")):
            result = await check_evaluation_model(db, user, publish=False)

        assert result.status == PreflightCheckStatus.FAILED
        assert "No API key configured" in result.detail


class TestCheckEndpointConnectivity:
    CONV_TRACKER = (
        "rhesis.backend.app.services.invokers.conversation"
        ".ConversationTracker.detect_stateless_mode"
    )
    CREATE_INVOKER = "rhesis.backend.app.services.invokers.create_invoker"

    @pytest.mark.asyncio
    async def test_successful_response(self):
        from rhesis.backend.app.services.preflight.checks import (
            check_endpoint_connectivity,
        )

        db = MagicMock()
        endpoint = MagicMock()

        mock_invoker = MagicMock()
        mock_invoker.invoke = AsyncMock(return_value={"output": "Hello!"})

        with (
            patch(self.CONV_TRACKER, return_value=False),
            patch(self.CREATE_INVOKER, return_value=mock_invoker),
        ):
            result = await check_endpoint_connectivity(db, endpoint, publish=False)

        assert result.status == PreflightCheckStatus.PASSED
        assert "Hello!" in result.detail

    @pytest.mark.asyncio
    async def test_timeout(self):
        from rhesis.backend.app.services.preflight.checks import (
            check_endpoint_connectivity,
        )

        db = MagicMock()
        endpoint = MagicMock()

        mock_invoker = MagicMock()
        mock_invoker.invoke = AsyncMock(side_effect=asyncio.TimeoutError())

        with (
            patch(self.CONV_TRACKER, return_value=False),
            patch(self.CREATE_INVOKER, return_value=mock_invoker),
        ):
            result = await check_endpoint_connectivity(db, endpoint, publish=False)

        assert result.status == PreflightCheckStatus.FAILED
        assert "timed out" in result.message.lower()


class TestValidateMetricsLoadable:
    MODEL_UTIL = (
        "rhesis.backend.app.utils.user_model_utils.get_evaluation_model_with_override"
    )
    VALIDATE_CONFIGS = "rhesis.backend.metrics.metric_config.validate_metric_configs"
    PREPARE_METRICS = "rhesis.backend.metrics.strategies.local.prepare_metrics"

    @pytest.mark.asyncio
    async def test_all_metrics_load(self):
        from rhesis.backend.app.services.preflight.checks import _validate_metrics_loadable

        db = MagicMock()
        user = MagicMock()
        user.organization_id = uuid4()

        metric1 = MagicMock()
        metric1.name = "Accuracy"
        metric2 = MagicMock()
        metric2.name = "Relevance"

        mock_model = MagicMock()
        mock_tasks = [MagicMock(), MagicMock()]

        with (
            patch(self.VALIDATE_CONFIGS, return_value=(["cfg1", "cfg2"], {})),
            patch(self.MODEL_UTIL, return_value=mock_model),
            patch(self.PREPARE_METRICS, return_value=mock_tasks),
        ):
            result = await _validate_metrics_loadable(db, user, [metric1, metric2])

        assert result.status == PreflightCheckStatus.PASSED
        assert "2" in result.message
        assert "Accuracy" in result.detail
        assert "Relevance" in result.detail

    @pytest.mark.asyncio
    async def test_some_metrics_invalid(self):
        from rhesis.backend.app.services.preflight.checks import _validate_metrics_loadable

        db = MagicMock()
        user = MagicMock()
        user.organization_id = uuid4()

        invalid_results = {
            "InvalidMetric_0": {"error": "Unknown class_name: FooMetric"},
        }

        with patch(self.VALIDATE_CONFIGS, return_value=([], invalid_results)):
            result = await _validate_metrics_loadable(db, user, [MagicMock()])

        assert result.status == PreflightCheckStatus.WARNING
        assert "failed to load" in result.message.lower()

    @pytest.mark.asyncio
    async def test_prepare_metrics_exception(self):
        from rhesis.backend.app.services.preflight.checks import _validate_metrics_loadable

        db = MagicMock()
        user = MagicMock()
        user.organization_id = uuid4()

        mock_model = MagicMock()

        with (
            patch(self.VALIDATE_CONFIGS, return_value=(["cfg1"], {})),
            patch(self.MODEL_UTIL, return_value=mock_model),
            patch(
                self.PREPARE_METRICS,
                side_effect=RuntimeError("Failed to create metric"),
            ),
        ):
            result = await _validate_metrics_loadable(db, user, [MagicMock()])

        assert result.status == PreflightCheckStatus.WARNING
        assert "Failed to create metric" in result.detail


class TestInferEndpointCapabilities:
    def test_all_fields_present(self):
        from rhesis.backend.app.services.preflight.checks import _infer_endpoint_capabilities

        endpoint = MagicMock()
        endpoint.response_mapping = {"context": "$.ctx", "tool_calls": "$.tools", "output": "$.out"}
        caps = _infer_endpoint_capabilities(endpoint)
        assert caps["context"] is True
        assert caps["tool_calls"] is True
        assert caps["metadata"] is False

    def test_empty_mapping(self):
        from rhesis.backend.app.services.preflight.checks import _infer_endpoint_capabilities

        endpoint = MagicMock()
        endpoint.response_mapping = {}
        caps = _infer_endpoint_capabilities(endpoint)
        assert caps["context"] is False
        assert caps["tool_calls"] is False
        assert caps["metadata"] is False

    def test_none_mapping(self):
        from rhesis.backend.app.services.preflight.checks import _infer_endpoint_capabilities

        endpoint = MagicMock()
        endpoint.response_mapping = None
        caps = _infer_endpoint_capabilities(endpoint)
        assert caps["context"] is False
        assert caps["tool_calls"] is False


class TestCheckMetricEndpointIssues:
    def _make_metric(self, name, class_name=None, context_required=False,
                     ground_truth_required=False):
        m = MagicMock()
        m.name = name
        m.class_name = class_name
        m.context_required = context_required
        m.ground_truth_required = ground_truth_required
        return m

    def test_no_issues_when_all_compatible(self):
        from rhesis.backend.app.services.preflight.checks import _check_metric_endpoint_issues

        metric = self._make_metric("Accuracy")
        caps = {"context": True, "tool_calls": True, "metadata": True}
        issues = _check_metric_endpoint_issues([metric], caps, 0, 10)
        assert issues == []

    def test_context_required_but_missing(self):
        from rhesis.backend.app.services.preflight.checks import _check_metric_endpoint_issues

        metric = self._make_metric("Faithfulness", context_required=True)
        caps = {"context": False, "tool_calls": False, "metadata": False}
        issues = _check_metric_endpoint_issues([metric], caps, 0, 10)
        assert len(issues) == 1
        assert "context" in issues[0]
        assert "Faithfulness" in issues[0]

    def test_ground_truth_required_all_missing(self):
        from rhesis.backend.app.services.preflight.checks import _check_metric_endpoint_issues

        metric = self._make_metric("CorrectnessMetric", ground_truth_required=True)
        caps = {"context": False, "tool_calls": False, "metadata": False}
        issues = _check_metric_endpoint_issues([metric], caps, 5, 5)
        assert len(issues) == 1
        assert "ground truth" in issues[0]
        assert "5 of 5" in issues[0]

    def test_ground_truth_required_partial_missing(self):
        from rhesis.backend.app.services.preflight.checks import _check_metric_endpoint_issues

        metric = self._make_metric("CorrectnessMetric", ground_truth_required=True)
        caps = {"context": False, "tool_calls": False, "metadata": False}
        issues = _check_metric_endpoint_issues([metric], caps, 3, 10)
        assert len(issues) == 1
        assert "3 of 10" in issues[0]

    def test_ground_truth_required_none_missing(self):
        from rhesis.backend.app.services.preflight.checks import _check_metric_endpoint_issues

        metric = self._make_metric("CorrectnessMetric", ground_truth_required=True)
        caps = {"context": False, "tool_calls": False, "metadata": False}
        issues = _check_metric_endpoint_issues([metric], caps, 0, 10)
        assert issues == []

    def test_tool_calls_class_missing(self):
        from rhesis.backend.app.services.preflight.checks import _check_metric_endpoint_issues

        metric = self._make_metric("ToolAccuracy", class_name="DeepEvalToolUse")
        caps = {"context": False, "tool_calls": False, "metadata": False}
        issues = _check_metric_endpoint_issues([metric], caps, 0, 10)
        assert len(issues) == 1
        assert "tool_calls" in issues[0]

    def test_tool_calls_class_present(self):
        from rhesis.backend.app.services.preflight.checks import _check_metric_endpoint_issues

        metric = self._make_metric("ToolAccuracy", class_name="DeepEvalToolUse")
        caps = {"context": False, "tool_calls": True, "metadata": False}
        issues = _check_metric_endpoint_issues([metric], caps, 0, 10)
        assert issues == []

    def test_multiple_metrics_multiple_issues(self):
        from rhesis.backend.app.services.preflight.checks import _check_metric_endpoint_issues

        m1 = self._make_metric("Faithfulness", context_required=True)
        m2 = self._make_metric("Correctness", ground_truth_required=True)
        caps = {"context": False, "tool_calls": False, "metadata": False}
        issues = _check_metric_endpoint_issues([m1, m2], caps, 2, 5)
        assert len(issues) == 2


class TestCheckMetricCompatibility:
    def _make_db(self, metrics=None, total_tests=5, missing_ground_truth=0):
        """Build a mock db with chained query returns for the compatibility check."""
        db = MagicMock()

        # Metrics query (for define_custom mode via Metric.id.in_)
        # Use a flexible side_effect on db.query so different models return different mocks
        metric_query = MagicMock()
        metric_query.filter.return_value.all.return_value = metrics or []

        ts_query = MagicMock()
        test_set_mock = MagicMock()
        test_set_mock.metrics = metrics or []
        ts_query.filter.return_value.first.return_value = test_set_mock

        # total_tests count
        total_count_query = MagicMock()
        total_count_query.filter.return_value.count.return_value = total_tests

        # missing ground truth count
        missing_count_query = MagicMock()
        missing_count_query.join.return_value.join.return_value.filter.return_value\
            .filter.return_value.count.return_value = missing_ground_truth

        return db

    @pytest.mark.asyncio
    async def test_no_metrics_skipped(self):
        from rhesis.backend.app.services.preflight.checks import check_metric_compatibility

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        endpoint = MagicMock()
        endpoint.response_mapping = {}
        ts_id = uuid4()

        with patch(
            "rhesis.backend.app.schemas.metric.MetricScope",
        ):
            result = await check_metric_compatibility(
                db, endpoint, ts_id, "define_custom", selected_metrics=[], publish=False
            )

        assert result.status == PreflightCheckStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_passed_when_all_compatible(self):
        from rhesis.backend.app.services.preflight.checks import check_metric_compatibility

        metric = MagicMock()
        metric.name = "Accuracy"
        metric.class_name = "AccuracyMetric"
        metric.metric_scope = ["Single-Turn"]  # real DB value
        metric.context_required = False
        metric.ground_truth_required = False

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [metric]

        endpoint = MagicMock()
        endpoint.response_mapping = {"output": "$.output"}
        ts_id = uuid4()

        result = await check_metric_compatibility(
            db, endpoint, ts_id, "define_custom",
            selected_metrics=[metric], publish=False
        )

        assert result.status == PreflightCheckStatus.PASSED
        assert "Accuracy" in result.detail

    @pytest.mark.asyncio
    async def test_warning_when_context_missing(self):
        from rhesis.backend.app.services.preflight.checks import check_metric_compatibility

        metric = MagicMock()
        metric.name = "Faithfulness"
        metric.class_name = "FaithfulnessMetric"
        metric.metric_scope = ["Single-Turn"]  # real DB value
        metric.context_required = True
        metric.ground_truth_required = False

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [metric]

        endpoint = MagicMock()
        endpoint.response_mapping = {"output": "$.output"}  # no context key
        ts_id = uuid4()

        result = await check_metric_compatibility(
            db, endpoint, ts_id, "define_custom",
            selected_metrics=[metric], publish=False
        )

        assert result.status == PreflightCheckStatus.WARNING
        assert "issue(s)" in result.message
        assert "context" in result.detail

    @pytest.mark.asyncio
    async def test_warning_on_partial_ground_truth(self):
        from rhesis.backend.app.services.preflight.checks import check_metric_compatibility

        metric = MagicMock()
        metric.name = "Correctness"
        metric.class_name = "CorrectnessMetric"
        metric.metric_scope = ["Single-Turn"]  # real DB value
        metric.context_required = False
        metric.ground_truth_required = True

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [metric]
        # total_tests count (filter().count())
        db.query.return_value.filter.return_value.count.return_value = 10
        # missing ground truth count (join().join().filter().filter().count())
        db.query.return_value.join.return_value.join.return_value\
            .filter.return_value.filter.return_value.count.return_value = 3

        endpoint = MagicMock()
        endpoint.response_mapping = {}
        ts_id = uuid4()

        result = await check_metric_compatibility(
            db, endpoint, ts_id, "define_custom",
            selected_metrics=[metric], publish=False
        )

        assert result.status == PreflightCheckStatus.WARNING
        assert "3" in result.detail
        assert "10" in result.detail

    @pytest.mark.asyncio
    async def test_multi_turn_skips_ground_truth_query(self):
        """Ground-truth query must not run for multi-turn scope (prompt_id is NULL)."""
        from rhesis.backend.app.services.preflight.checks import check_metric_compatibility

        metric = MagicMock()
        metric.name = "ConvJudge"
        metric.class_name = "ConversationalJudge"
        metric.metric_scope = ["Multi-Turn"]  # real DB value
        metric.context_required = False
        metric.ground_truth_required = True  # even if set, should not trigger query

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [metric]

        endpoint = MagicMock()
        endpoint.response_mapping = {}
        ts_id = uuid4()

        result = await check_metric_compatibility(
            db, endpoint, ts_id, "define_custom",
            selected_metrics=[metric], is_multi_turn=True, publish=False
        )

        # No ground-truth warning should appear since the query is skipped
        assert result.status == PreflightCheckStatus.PASSED
        # The Prompt-join count query must not have been called
        db.query.return_value.join.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_returns_failed(self):
        from rhesis.backend.app.services.preflight.checks import check_metric_compatibility

        db = MagicMock()
        db.query.side_effect = RuntimeError("db gone")

        endpoint = MagicMock()
        ts_id = uuid4()

        result = await check_metric_compatibility(
            db, endpoint, ts_id, "define_custom",
            selected_metrics=[MagicMock()], publish=False
        )

        assert result.status == PreflightCheckStatus.FAILED
        assert "db gone" in result.detail


class TestRunPreflightChecksMulti:
    @pytest.mark.asyncio
    async def test_reuse_skips_connectivity(self):
        from rhesis.backend.app.services.preflight.orchestrator import (
            run_preflight_checks_multi,
        )

        db = MagicMock()
        user = MagicMock()
        user.organization_id = uuid4()
        ts_id = uuid4()

        endpoint = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = endpoint

        async def mock_check(*args, **kwargs):
            return _make_result(args[0] if isinstance(args[0], str) else "check",
                                PreflightCheckStatus.PASSED)

        with (
            patch(
                "rhesis.backend.app.services.preflight.orchestrator"
                ".check_evaluation_model",
                new_callable=AsyncMock,
                return_value=_make_result(
                    CHECK_EVALUATION_MODEL, PreflightCheckStatus.PASSED
                ),
            ),
            patch(
                "rhesis.backend.app.services.preflight.orchestrator"
                ".check_test_set_not_empty",
                new_callable=AsyncMock,
                return_value=_make_result(
                    CHECK_TEST_SET_NOT_EMPTY, PreflightCheckStatus.PASSED
                ),
            ),
            patch(
                "rhesis.backend.app.services.preflight.orchestrator"
                ".check_behavior_metric_coverage",
                new_callable=AsyncMock,
                return_value=_make_result(
                    CHECK_BEHAVIOR_METRIC_COVERAGE, PreflightCheckStatus.PASSED
                ),
            ),
            patch(
                "rhesis.backend.app.services.preflight.orchestrator"
                ".check_metric_compatibility",
                new_callable=AsyncMock,
                return_value=_make_result(
                    CHECK_METRIC_COMPATIBILITY, PreflightCheckStatus.PASSED
                ),
            ),
            patch(
                "rhesis.backend.app.services.preflight.orchestrator"
                ".check_metric_functionality",
                new_callable=AsyncMock,
                return_value=_make_result(
                    CHECK_METRIC_FUNCTIONALITY, PreflightCheckStatus.PASSED
                ),
            ),
        ):
            results = await run_preflight_checks_multi(
                db=db,
                user=user,
                test_sets=[(ts_id, "Test Set", False)],
                endpoint_id=uuid4(),
                scoring_target="reuse",
                publish=False,
            )

        statuses = {r.check_id: r.status for r in results}
        assert statuses[CHECK_ENDPOINT_CONNECTIVITY] == PreflightCheckStatus.SKIPPED

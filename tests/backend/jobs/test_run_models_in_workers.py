"""Both worker paths build only the models the run uses (issue #2853).

Batch and sequential used to carry their own copy of the same block, which built
the execution and the evaluation model for every run. They now share
``app/services/run_models.py``.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.jobs.execution.batch.context import (
    ExecutionContext,
    prefetch_execution_context,
)
from rhesis.backend.jobs.execution.batch.runner import run_batch
from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially

_RESOLVE = "rhesis.backend.app.utils.user_model_utils.resolve_model"
_GET_USER = "rhesis.backend.app.services.run_models.get_user_by_id"
_RECORD = "rhesis.backend.app.services.run_models.record_resolved_evaluation_model"

SDK_ONLY = {"metric_backends": ["sdk"], "has_multi_turn": False}
LLM_METRIC = {"metric_backends": ["rhesis", "sdk"], "has_multi_turn": False}
MULTI_TURN = {"metric_backends": ["sdk"], "has_multi_turn": True}

# plan, replay, purposes built
CASES = [
    pytest.param(SDK_ONLY, False, [], id="sdk-only"),
    pytest.param(LLM_METRIC, False, ["evaluation"], id="llm-metric"),
    pytest.param(MULTI_TURN, False, ["evaluation", "execution"], id="multi-turn"),
    pytest.param(MULTI_TURN, True, ["evaluation"], id="multi-turn-rescore"),
]


def _resolve_by_purpose(_session, _user, purpose, override=None):
    return f"{purpose}-model"


def _expected(purposes):
    return {
        "evaluation": "evaluation-model" if "evaluation" in purposes else None,
        "execution": "execution-model" if "execution" in purposes else None,
    }


def _config(replay):
    config = MagicMock()
    config.id = uuid4()
    config.attributes = {"reference_test_run_id": "run-0"} if replay else {}
    config.organization_id = uuid4()
    config.user_id = uuid4()
    config.project_id = None
    config.test_set_id = uuid4()
    config.endpoint_id = uuid4()
    return config


def _run(plan):
    run = MagicMock()
    run.id = uuid4()
    run.attributes = {"metric_plan": plan, "task_id": "task-1"}
    return run


@pytest.mark.unit
class TestBatchPrefetchBuildsOnlyNeededModels:
    @pytest.mark.parametrize("plan, replay, purposes", CASES)
    def test_prefetch(self, plan, replay, purposes):
        test = MagicMock()
        test.id = uuid4()
        test.requirement_id = None
        config = _config(replay)
        endpoint = MagicMock()
        endpoint.project_id = None

        with (
            patch("rhesis.backend.app.database.bind_scope_to_session"),
            patch("rhesis.backend.app.services.test_set.get_test_set", return_value=MagicMock()),
            patch("rhesis.backend.app.crud.endpoint.get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.invokers.auth.manager.AuthenticationManager"),
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_and_prompt",
                return_value=(test, "prompt", "expected"),
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=([], "none"),
            ),
            patch(
                "rhesis.backend.app.crud.test_result.get_stored_outputs_for_run", return_value={}
            ),
            patch(_RESOLVE, side_effect=_resolve_by_purpose) as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            ctx = prefetch_execution_context(
                MagicMock(),
                config,
                _run(plan),
                [test],
                reference_test_run_id="run-0" if replay else None,
            )

        assert sorted(c.args[2] for c in resolve.call_args_list) == purposes
        expected = _expected(purposes)
        assert ctx.evaluation_model == expected["evaluation"]
        assert ctx.execution_model == expected["execution"]


@pytest.mark.unit
class TestSequentialBuildsOnlyNeededModels:
    @pytest.mark.parametrize("plan, replay, purposes", CASES)
    def test_sequential(self, plan, replay, purposes):
        passed = {}

        async def _fake_execute(**kwargs):
            passed.update(kwargs)
            return {"test_id": kwargs["test_id"], "status": "succeeded"}

        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fake_execute,
            ),
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-1"),
            ),
            patch("rhesis.backend.jobs.execution.sequential.is_task_revoked", return_value=False),
            patch(_RESOLVE, side_effect=_resolve_by_purpose) as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            execute_tests_sequentially(
                MagicMock(),
                _config(replay),
                _run(plan),
                [MagicMock(id="t1")],
                reference_test_run_id="run-0" if replay else None,
            )

        assert sorted(c.args[2] for c in resolve.call_args_list) == purposes
        expected = _expected(purposes)
        assert passed["evaluation_model"] == expected["evaluation"]
        assert passed["execution_model"] == expected["execution"]


@pytest.mark.unit
class TestMetricEditedAfterDispatch:
    """The plan is frozen at dispatch. A metric that became LLM-backed before the
    worker picked the run up must still get the evaluation model, not an SDK default."""

    def test_batch(self):
        test = MagicMock()
        test.id = uuid4()
        test.requirement_id = None
        endpoint = MagicMock()
        endpoint.project_id = None
        judge_metric = MagicMock()

        with (
            patch("rhesis.backend.app.database.bind_scope_to_session"),
            patch("rhesis.backend.app.services.test_set.get_test_set", return_value=MagicMock()),
            patch("rhesis.backend.app.crud.endpoint.get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.invokers.auth.manager.AuthenticationManager"),
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_and_prompt",
                return_value=(test, "prompt", "expected"),
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=([judge_metric], "test_set"),
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[judge_metric],
            ),
            patch(
                "rhesis.backend.jobs.execution.batch.context.metric_model_to_config",
                return_value=MagicMock(backend="rhesis", parameters={}),
            ),
            patch(_RESOLVE, side_effect=_resolve_by_purpose) as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            ctx = prefetch_execution_context(MagicMock(), _config(False), _run(SDK_ONLY), [test])

        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation"]
        assert ctx.evaluation_model == "evaluation-model"
        assert ctx.execution_model is None

    def test_sequential(self):
        passed = {}

        async def _fake_execute(**kwargs):
            passed.update(kwargs)
            return {"test_id": kwargs["test_id"], "status": "succeeded"}

        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fake_execute,
            ),
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-1"),
            ),
            patch("rhesis.backend.jobs.execution.sequential.is_task_revoked", return_value=False),
            patch(
                "rhesis.backend.jobs.execution.sequential.get_live_metric_backends",
                return_value=["rhesis"],
            ),
            patch(_RESOLVE, side_effect=_resolve_by_purpose) as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            execute_tests_sequentially(
                MagicMock(), _config(False), _run(SDK_ONLY), [MagicMock(id="t1")]
            )

        assert [c.args[2] for c in resolve.call_args_list] == ["evaluation"]
        assert passed["evaluation_model"] == "evaluation-model"
        assert passed["execution_model"] is None

    def test_batch_test_that_became_multi_turn(self):
        test = MagicMock()
        test.id = uuid4()
        test.requirement_id = None
        endpoint = MagicMock()
        endpoint.project_id = None

        with (
            patch("rhesis.backend.app.database.bind_scope_to_session"),
            patch("rhesis.backend.app.services.test_set.get_test_set", return_value=MagicMock()),
            patch("rhesis.backend.app.crud.endpoint.get_endpoint", return_value=endpoint),
            patch("rhesis.backend.app.services.invokers.auth.manager.AuthenticationManager"),
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_and_prompt",
                return_value=(test, "prompt", "expected"),
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=([], "none"),
            ),
            patch("rhesis.backend.jobs.execution.modes.is_multi_turn_test", return_value=True),
            patch(_RESOLVE, side_effect=_resolve_by_purpose) as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            ctx = prefetch_execution_context(MagicMock(), _config(False), _run(SDK_ONLY), [test])

        assert sorted(c.args[2] for c in resolve.call_args_list) == ["evaluation", "execution"]
        assert ctx.evaluation_model == "evaluation-model"
        assert ctx.execution_model == "execution-model"

    def test_sequential_test_that_became_multi_turn(self):
        passed = {}

        async def _fake_execute(**kwargs):
            passed.update(kwargs)
            return {"test_id": kwargs["test_id"], "status": "succeeded"}

        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fake_execute,
            ),
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-1"),
            ),
            patch("rhesis.backend.jobs.execution.sequential.is_task_revoked", return_value=False),
            patch("rhesis.backend.jobs.execution.sequential.is_multi_turn_test", return_value=True),
            patch(_RESOLVE, side_effect=_resolve_by_purpose) as resolve,
            patch(_GET_USER, return_value=MagicMock()),
            patch(_RECORD),
        ):
            execute_tests_sequentially(
                MagicMock(), _config(False), _run(SDK_ONLY), [MagicMock(id="t1")]
            )

        assert sorted(c.args[2] for c in resolve.call_args_list) == ["evaluation", "execution"]
        assert passed["evaluation_model"] == "evaluation-model"
        assert passed["execution_model"] == "execution-model"

    def test_live_backends_are_read_once_per_requirement(self):
        from rhesis.backend.jobs.execution.executors.data import get_live_metric_backends

        tests = [
            MagicMock(requirement_id="req-a"),
            MagicMock(requirement_id="req-a"),
            MagicMock(requirement_id="req-b"),
        ]
        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                side_effect=[(["metric-a"], "requirement"), (["metric-b"], "requirement")],
            ) as get_metrics,
            patch(
                "rhesis.backend.app.services.run_models.metric_backends",
                return_value=["rhesis", "sdk"],
            ) as backends,
        ):
            result = get_live_metric_backends(MagicMock(), tests, MagicMock(), "org-1", "user-1")

        assert get_metrics.call_count == 2
        assert backends.call_args.args[1] == ["metric-a", "metric-b"]
        assert result == ["rhesis", "sdk"]

    def test_shared_metrics_are_read_once_for_the_whole_run(self):
        from rhesis.backend.jobs.execution.executors.data import get_live_metric_backends

        tests = [MagicMock(requirement_id="req-a"), MagicMock(requirement_id="req-b")]
        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=(["metric-a"], "test_set"),
            ) as get_metrics,
            patch("rhesis.backend.app.services.run_models.metric_backends", return_value=["sdk"]),
        ):
            get_live_metric_backends(MagicMock(), tests, MagicMock())

        assert get_metrics.call_count == 1


@pytest.mark.asyncio
async def test_a_batch_rescore_of_multi_turn_tests_starts_no_penelope():
    """A re-score has no execution model, and Penelope would build its own default."""
    ctx = ExecutionContext(
        test_config=MagicMock(),
        test_run=MagicMock(),
        test_set=MagicMock(),
        endpoint=MagicMock(),
        organization_id="org-1",
        user_id="user-1",
        recovery_rounds=0,
        execution_model=None,
        stored_outputs={"t1": {"conversation_summary": []}},
        test_data={"t1": {"test": MagicMock()}},
    )

    with (
        patch("rhesis.backend.jobs.execution.batch.runner.is_multi_turn_test", return_value=True),
        patch("rhesis.penelope.PenelopeAgent") as agent_class,
        patch(
            "rhesis.backend.jobs.execution.batch.runner._run_gather",
            new=AsyncMock(return_value=[]),
        ) as run_gather,
    ):
        await run_batch(ctx, ["t1"])

    agent_class.assert_not_called()
    # penelope_agent is the fourth positional argument of _run_gather.
    assert run_gather.call_args.args[3] is None

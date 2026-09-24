"""A re-score judges a run's stored outputs again: it must not call the endpoint,
and it scores Goal Achievement on multi-turn tests the way a live run does.

The batch path used to receive ``reference_test_run_id`` and ignore it, so a
Parallel re-score (every re-score started from the UI) re-ran every test live.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.jobs.execution.batch.context import ExecutionContext
from rhesis.backend.jobs.execution.batch.evaluation import evaluate_metrics
from rhesis.backend.jobs.execution.batch.invocation import run_test
from rhesis.backend.jobs.execution.constants import (
    CONVERSATION_SUMMARY_KEY,
    PENELOPE_MESSAGE_KEY,
    TARGET_RESPONSE_KEY,
)
from rhesis.backend.jobs.execution.evaluation import with_default_goal_metric

_CONVERSATION = {
    CONVERSATION_SUMMARY_KEY: [{PENELOPE_MESSAGE_KEY: "Book a flight", TARGET_RESPONSE_KEY: "OK"}]
}


def _ctx(**overrides) -> ExecutionContext:
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


def _config(name: str, class_name: str) -> MagicMock:
    mc = MagicMock()
    mc.name = name
    mc.class_name = class_name
    mc.metric_scope = ["Multi-Turn"]
    return mc


def _multi_turn_test() -> MagicMock:
    test = MagicMock()
    test.id = "test-1"
    test.test_configuration = {"goal": "Book a flight", "instructions": "Be polite"}
    test.test_metadata = None
    return test


def _evaluator() -> MagicMock:
    evaluator = MagicMock()
    future = asyncio.Future()
    future.set_result({})
    evaluator.a_evaluate = MagicMock(return_value=future)
    return evaluator


class TestBatchReplay:
    @pytest.mark.asyncio
    async def test_rescore_replays_the_stored_output_without_calling_the_endpoint(self):
        ctx = _ctx(reference_test_run_id="run-0", stored_outputs={"test-1": _CONVERSATION})

        with (
            patch(
                "rhesis.backend.jobs.execution.batch.invocation._run_multi_turn",
                new=AsyncMock(side_effect=AssertionError("endpoint called")),
            ),
            patch(
                "rhesis.backend.jobs.execution.batch.invocation._run_single_turn",
                new=AsyncMock(side_effect=AssertionError("endpoint called")),
            ),
        ):
            result = await run_test(ctx, MagicMock(), "test-1", "", {}, True, [])

        assert result["output"] == _CONVERSATION
        assert result["output"] is not _CONVERSATION
        assert result["penelope_metrics"] == {}

    @pytest.mark.asyncio
    async def test_missing_stored_output_fails_the_test(self):
        ctx = _ctx(reference_test_run_id="run-0", stored_outputs={})

        with pytest.raises(ValueError, match="No stored output"):
            await run_test(ctx, MagicMock(), "test-1", "", {}, False, [])


class TestRescoreScoresTheGoal:
    @pytest.mark.asyncio
    async def test_rescore_uses_penelopes_judge_not_the_listed_one(self):
        listed_goal = _config("Booking Goal", "GoalAchievementJudge")
        accuracy = _config("Accuracy", "ConversationalJudge")
        ctx = _ctx(
            stored_outputs={"test-1": _CONVERSATION},
            per_test_metric_configs={"test-1": [listed_goal, accuracy]},
        )
        evaluator = _evaluator()

        await evaluate_metrics(
            ctx, evaluator, _multi_turn_test(), "test-1", dict(_CONVERSATION), "", "", True, {}
        )

        kwargs = evaluator.a_evaluate.call_args.kwargs
        assert [(m.name, m.class_name) for m in kwargs["metrics"]] == [
            ("Accuracy", "ConversationalJudge"),
            ("Goal Achievement", "GoalAchievementJudge"),
        ]
        assert kwargs["instructions"] == "Be polite"

    @pytest.mark.asyncio
    async def test_rescore_scores_the_goal_even_with_no_listed_metrics(self):
        ctx = _ctx(stored_outputs={"test-1": _CONVERSATION}, per_test_metric_configs={"x": []})
        evaluator = _evaluator()

        await evaluate_metrics(
            ctx, evaluator, _multi_turn_test(), "test-1", dict(_CONVERSATION), "", "", True, {}
        )

        metrics = evaluator.a_evaluate.call_args.kwargs["metrics"]
        assert [m.name for m in metrics] == ["Goal Achievement"]

    @pytest.mark.asyncio
    async def test_rescore_with_unusable_contract_scores_nothing(self):
        ctx = _ctx(
            stored_outputs={"test-1": _CONVERSATION},
            per_test_metric_configs={"test-1": [_config("Accuracy", "ConversationalJudge")]},
        )
        evaluator = _evaluator()

        with patch(
            "rhesis.backend.jobs.execution.batch.evaluation.stored_contract_for_rescore",
            return_value=(False, None),
        ):
            results = await evaluate_metrics(
                ctx, evaluator, _multi_turn_test(), "test-1", dict(_CONVERSATION), "", "", True, {}
            )

        assert results == {}
        evaluator.a_evaluate.assert_not_called()

    @pytest.mark.asyncio
    async def test_live_run_leaves_the_goal_to_penelope(self):
        ctx = _ctx(
            per_test_metric_configs={
                "test-1": [
                    _config("Booking Goal", "GoalAchievementJudge"),
                    _config("Accuracy", "ConversationalJudge"),
                ]
            }
        )
        evaluator = _evaluator()
        penelope = {"Goal Achievement": {"is_successful": False}}

        results = await evaluate_metrics(
            ctx,
            evaluator,
            _multi_turn_test(),
            "test-1",
            dict(_CONVERSATION),
            "",
            "",
            True,
            penelope,
        )

        metrics = evaluator.a_evaluate.call_args.kwargs["metrics"]
        assert [m.name for m in metrics] == ["Accuracy"]
        assert results["Goal Achievement"] == {"is_successful": False}


def test_default_goal_metric_replaces_a_listed_one():
    configs = with_default_goal_metric(
        [_config("Booking Goal", "GoalAchievementJudge"), _config("Accuracy", "NumericJudge")]
    )

    assert [(c.name, c.class_name) for c in configs] == [
        ("Accuracy", "NumericJudge"),
        ("Goal Achievement", "GoalAchievementJudge"),
    ]
    assert configs[-1].threshold == 0.7

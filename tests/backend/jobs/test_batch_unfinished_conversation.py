"""#3014: a conversation Penelope stopped early is persisted unscored on the batch path."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.jobs.execution.batch.runner import _execute_single_test

RUNNER = "rhesis.backend.jobs.execution.batch.runner"
PASSING_GOAL = {"Goal Achievement": {"is_successful": True, "score": 1.0}}


def _ctx():
    ctx = MagicMock()
    ctx.existing_result_ids = set()
    ctx.test_data = {"test-1": {"test": MagicMock(), "prompt_content": "", "expected_response": ""}}
    ctx.input_files = {}
    ctx.per_test_timeout = 30
    ctx.get_metric_configs_for_test.return_value = [{"name": "Goal Achievement"}]
    return ctx


async def _run(status):
    output = {"status": status, "conversation_summary": [{"turn": 1, "success": True}]}
    evaluator = MagicMock()
    with (
        patch(f"{RUNNER}.is_multi_turn_test", return_value=True),
        patch(
            f"{RUNNER}.run_test",
            new=AsyncMock(return_value={"output": output, "penelope_metrics": PASSING_GOAL}),
        ),
        patch(f"{RUNNER}.evaluate_metrics", new=AsyncMock(return_value=PASSING_GOAL)) as evaluate,
        patch("rhesis.backend.jobs.execution.batch.persist.persist_result") as persist,
    ):
        result = await _execute_single_test(
            _ctx(), "test-1", asyncio.Semaphore(1), evaluator=evaluator
        )
    return result, evaluate, persist.call_args.args[4]


@pytest.mark.asyncio
async def test_stopped_early_is_persisted_without_metrics():
    result, evaluate, persisted_metrics = await _run("error")

    evaluate.assert_not_called()
    assert persisted_metrics == {}
    assert result["status"] == "succeeded"


@pytest.mark.asyncio
async def test_finished_conversation_is_still_scored():
    _, evaluate, persisted_metrics = await _run("max_turns")

    evaluate.assert_called_once()
    assert persisted_metrics == PASSING_GOAL

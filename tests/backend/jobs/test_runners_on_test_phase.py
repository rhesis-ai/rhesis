"""Tests for the on_test_phase EVALUATING callback in SingleTurnRunner and
MultiTurnRunner.

This is what gives the sequential execution path a real generating ->
evaluating boundary for the Summary grid's animation. Batch already had one
at the orchestration layer; this thread it down to where sequential's
equivalent seam actually lives -- inside these runners, between the output
provider call and metric evaluation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.services.test_run_timing import TestPhase
from rhesis.backend.jobs.execution.constants import CONVERSATION_SUMMARY_KEY
from rhesis.backend.jobs.execution.executors.output_providers import TestOutput
from rhesis.backend.jobs.execution.executors.runners import (
    MultiTurnRunner,
    SingleTurnRunner,
)


@pytest.mark.asyncio
class TestSingleTurnRunnerOnTestPhase:
    async def _run(self, on_test_phase, response=None, http_error=False):
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response=response
                if response is not None
                else ({"status_code": 500} if http_error else {"output": "ok"}),
                execution_time=0,
                source="test_result",
            )
        )
        mock_test = MagicMock()
        mock_test.id = "test-1"

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.runners.get_test_metrics",
                return_value=[],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.runners.prepare_metric_configs",
                return_value=[],
            ),
        ):
            runner = SingleTurnRunner()
            return await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                user_id="user-1",
                prompt_content="What is 2+2?",
                expected_response="4",
                evaluate_metrics=False,
                output_provider=mock_provider,
                on_test_phase=on_test_phase,
            )

    async def test_fires_evaluating_once_output_is_obtained(self):
        calls = []
        await self._run(lambda test_id, phase: calls.append((test_id, phase)))
        assert calls == [("test-1", TestPhase.EVALUATING)]

    async def test_fires_even_when_no_metrics_will_run(self):
        # evaluate_metrics=False in _run -- the callback still fires, matching
        # the batch path firing unconditionally right after generation.
        calls = []
        await self._run(
            lambda test_id, phase: calls.append((test_id, phase)),
            response={"output": "ok"},
        )
        assert ("test-1", TestPhase.EVALUATING) in calls

    async def test_fires_even_on_an_http_error_response(self):
        # An HTTP error still means generation finished -- the test just has
        # no metrics to evaluate. Matches batch, which fires unconditionally
        # right after generation succeeds regardless of what the output was.
        calls = []
        await self._run(
            lambda test_id, phase: calls.append((test_id, phase)),
            http_error=True,
        )
        assert calls == [("test-1", TestPhase.EVALUATING)]

    async def test_is_optional(self):
        # Must not raise when omitted -- the in-place/playground service
        # never passes this.
        exec_time, result, metrics = await self._run(None)
        assert result == {"output": "ok"}

    async def test_a_raising_callback_does_not_break_execution(self):
        def boom(test_id, phase):
            raise RuntimeError("boom")

        exec_time, result, metrics = await self._run(boom)
        assert result == {"output": "ok"}


@pytest.mark.asyncio
class TestMultiTurnRunnerOnTestPhase:
    async def _run(self, on_test_phase):
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response={CONVERSATION_SUMMARY_KEY: [{"role": "assistant", "content": "Hi"}]},
                execution_time=0,
                metrics={},
                source="test_result",
            )
        )
        mock_test = MagicMock()
        mock_test.id = "test-2"
        mock_test.test_configuration = {"goal": "Greet"}

        with patch(
            "rhesis.backend.jobs.execution.executors.runners.evaluate_multi_turn_metrics",
            return_value={},
        ):
            runner = MultiTurnRunner()
            return await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                user_id="user-1",
                output_provider=mock_provider,
                on_test_phase=on_test_phase,
            )

    async def test_fires_evaluating_once_output_is_obtained(self):
        calls = []
        await self._run(lambda test_id, phase: calls.append((test_id, phase)))
        assert calls == [("test-2", TestPhase.EVALUATING)]

    async def test_is_optional(self):
        exec_time, trace, metrics = await self._run(None)
        assert trace[CONVERSATION_SUMMARY_KEY]

    async def test_a_raising_callback_does_not_break_execution(self):
        def boom(test_id, phase):
            raise RuntimeError("boom")

        exec_time, trace, metrics = await self._run(boom)
        assert trace[CONVERSATION_SUMMARY_KEY]

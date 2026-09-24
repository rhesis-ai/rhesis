"""A re-score judges a run's stored outputs again: it must not call the endpoint.

The batch path used to receive ``reference_test_run_id`` and ignore it, so a
Parallel re-score (every re-score started from the UI) re-ran every test live.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.jobs.execution.batch.context import ExecutionContext
from rhesis.backend.jobs.execution.batch.invocation import run_test
from rhesis.backend.jobs.execution.constants import (
    CONVERSATION_SUMMARY_KEY,
    PENELOPE_MESSAGE_KEY,
    TARGET_RESPONSE_KEY,
)

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

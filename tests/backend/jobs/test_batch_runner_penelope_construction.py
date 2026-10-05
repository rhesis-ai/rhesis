"""The batch runner's Penelope construction stamps a bare execution model.

``ctx.execution_model`` can still be a plain provider string --
``resolve_default_hosted_model``'s own construction-failure fallback -- and
Penelope is a separate package that cannot apply a usage-provenance stamp
itself. Without routing it through ``ensure_language_model`` first, that
string crosses into Penelope, which builds it via its own unstamped
``get_model(model)`` call, and its tokens fall back to the process-wide
sink's unstamped heuristic instead of being definitively attributed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.jobs.execution.batch.context import ExecutionContext
from rhesis.backend.jobs.execution.batch.runner import run_batch


def _make_execution_context(**overrides) -> ExecutionContext:
    defaults = dict(
        test_config=MagicMock(),
        test_run=MagicMock(),
        test_set=MagicMock(),
        endpoint=MagicMock(),
        organization_id="org-1",
        user_id="user-1",
        recovery_rounds=0,
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


@pytest.mark.asyncio
async def test_string_execution_model_is_stamped_before_penelope_receives_it():
    stamped_model = MagicMock()
    stamped_model.warmup = AsyncMock()

    ctx = _make_execution_context(
        execution_model="vertex_ai/gemini-2.5-flash",
        test_data={"t1": {"test": MagicMock()}},
    )

    with (
        patch(
            "rhesis.backend.jobs.execution.batch.runner.is_multi_turn_test",
            return_value=True,
        ),
        patch(
            "rhesis.backend.app.utils.user_model_utils.ensure_language_model",
            return_value=stamped_model,
        ) as mock_ensure,
        patch("rhesis.penelope.PenelopeAgent") as mock_agent_class,
        patch(
            "rhesis.backend.jobs.execution.batch.runner._run_gather",
            new=AsyncMock(return_value=[]),
        ),
    ):
        mock_agent_class.return_value.model = stamped_model
        await run_batch(ctx, ["t1"])

    mock_ensure.assert_called_once_with("vertex_ai/gemini-2.5-flash")
    mock_agent_class.assert_called_once_with(model=stamped_model)


@pytest.mark.asyncio
async def test_no_execution_model_starts_no_penelope():
    """Penelope would build its own default: not the model the run chose. Each
    multi-turn test reports an Error instead (see ``_run_multi_turn``)."""
    ctx = _make_execution_context(
        execution_model=None,
        test_data={"t1": {"test": MagicMock()}},
    )

    with (
        patch(
            "rhesis.backend.jobs.execution.batch.runner.is_multi_turn_test",
            return_value=True,
        ),
        patch("rhesis.penelope.PenelopeAgent") as mock_agent_class,
        patch(
            "rhesis.backend.jobs.execution.batch.runner._run_gather",
            new=AsyncMock(return_value=[]),
        ) as run_gather,
    ):
        await run_batch(ctx, ["t1"])

    mock_agent_class.assert_not_called()
    assert run_gather.call_args.args[3] is None


@pytest.mark.asyncio
async def test_a_multi_turn_test_without_penelope_reports_an_error():
    from rhesis.backend.jobs.execution.batch.invocation import _run_multi_turn
    from rhesis.backend.jobs.execution.constants import NO_EXECUTION_MODEL_ERROR

    test = MagicMock()
    test.test_configuration = {"goal": "Book a flight"}

    with patch(
        "rhesis.backend.jobs.execution.batch.invocation.resolve_contract_lazy"
    ) as resolve_contract:
        result = await _run_multi_turn(_make_execution_context(), test, "t1", {}, [], None)

    resolve_contract.assert_not_called()
    assert result["output"] == {"status": "error", "error": NO_EXECUTION_MODEL_ERROR}
    assert result["contract_usable"] is False
    assert result["penelope_metrics"] == {}


@pytest.mark.asyncio
async def test_an_already_resolved_model_is_passed_through_unchanged():
    """The normal case: a real BaseLLM, already stamped by
    resolve_model -- ensure_language_model must not
    reconstruct it."""
    resolved_model = MagicMock()
    resolved_model.warmup = AsyncMock()

    ctx = _make_execution_context(
        execution_model=resolved_model,
        test_data={"t1": {"test": MagicMock()}},
    )

    with (
        patch(
            "rhesis.backend.jobs.execution.batch.runner.is_multi_turn_test",
            return_value=True,
        ),
        patch("rhesis.penelope.PenelopeAgent") as mock_agent_class,
        patch(
            "rhesis.backend.jobs.execution.batch.runner._run_gather",
            new=AsyncMock(return_value=[]),
        ),
    ):
        mock_agent_class.return_value.model = resolved_model
        await run_batch(ctx, ["t1"])

    mock_agent_class.assert_called_once_with(model=resolved_model)

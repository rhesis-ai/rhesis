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
from rhesis.sdk.models.base import BaseLLM


class _StubLLM(BaseLLM):
    """A real BaseLLM so stamp_usage_provenance's isinstance check passes."""

    PROVIDER = "stub"

    def load_model(self, *args, **kwargs):
        return None

    def generate_batch(self, *args, **kwargs):
        return []


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
async def test_penelopes_own_default_model_is_stamped_after_construction():
    """With no model to hand in, Penelope builds its own default. That runs
    on this deployment's credentials like any other default, so it is stamped
    on the instance afterwards -- which is what lets accrue_model_tokens
    treat an unstamped model as a plain bug rather than a category needing an
    api-key heuristic to disambiguate."""
    ctx = _make_execution_context(
        execution_model=None,
        test_data={"t1": {"test": MagicMock()}},
    )
    penelopes_own_model = _StubLLM("vertex_ai/gemini-2.5-flash")
    penelopes_own_model.warmup = AsyncMock()

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
        mock_agent_class.return_value.model = penelopes_own_model
        await run_batch(ctx, ["t1"])

    mock_agent_class.assert_called_once_with()
    assert penelopes_own_model.usage_metered is True


@pytest.mark.asyncio
async def test_an_already_resolved_model_is_passed_through_unchanged():
    """The normal case: a real BaseLLM, already stamped by
    get_execution_model_with_override -- ensure_language_model must not
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

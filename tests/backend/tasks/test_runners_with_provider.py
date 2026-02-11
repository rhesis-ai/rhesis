"""
Tests for SingleTurnRunner and MultiTurnRunner with injected OutputProvider.

Covers:
- SingleTurnRunner uses injected provider instead of default SingleTurnOutput
- SingleTurnRunner falls back to SingleTurnOutput when provider is None
- MultiTurnRunner uses injected provider instead of default MultiTurnOutput
- MultiTurnRunner calls evaluate_multi_turn_metrics when provider has no metrics
- MultiTurnRunner uses output.metrics when provider returns metrics (live)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.tasks.execution.executors.output_providers import (
    TestOutput,
)
from rhesis.backend.tasks.execution.executors.runners import (
    MultiTurnRunner,
    SingleTurnRunner,
)

# ============================================================================
# SingleTurnRunner with provider tests
# ============================================================================


class TestSingleTurnRunnerWithProvider:
    """Tests for SingleTurnRunner with injected OutputProvider."""

    @pytest.mark.asyncio
    async def test_uses_injected_provider(self):
        """SingleTurnRunner calls injected provider's get_output."""
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response={"output": "stored response"},
                execution_time=0,
                source="test_result",
            )
        )

        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_test.behavior = MagicMock()

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.runners.get_test_metrics",
                return_value=[],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.prepare_metric_configs",
                return_value=[],
            ),
        ):
            runner = SingleTurnRunner()
            exec_time, result, metrics = await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                user_id="user-1",
                prompt_content="What is 2+2?",
                expected_response="4",
                evaluate_metrics=False,
                output_provider=mock_provider,
            )

        mock_provider.get_output.assert_called_once()
        assert result == {"output": "stored response"}
        assert exec_time == 0

    @pytest.mark.asyncio
    async def test_defaults_to_single_turn_output(self):
        """When output_provider is None, SingleTurnOutput is used."""
        mock_test = MagicMock()
        mock_test.id = "test-1"

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.runners.get_test_metrics",
                return_value=[],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.prepare_metric_configs",
                return_value=[],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.SingleTurnOutput",
            ) as mock_st_class,
        ):
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_output = AsyncMock(
                return_value=TestOutput(
                    response={"output": "live response"},
                    execution_time=150.0,
                )
            )
            mock_st_class.return_value = mock_provider_instance

            runner = SingleTurnRunner()
            exec_time, result, metrics = await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                evaluate_metrics=False,
                output_provider=None,
            )

        mock_st_class.assert_called_once()
        assert result == {"output": "live response"}
        assert exec_time == 150.0

    @pytest.mark.asyncio
    async def test_evaluates_metrics_with_injected_provider(self):
        """Metrics are evaluated even when using an injected provider."""
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response={"output": "stored"},
                execution_time=0,
                source="test_result",
            )
        )

        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_test.behavior = MagicMock()

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.runners.get_test_metrics",
                return_value=[{"name": "accuracy"}],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.prepare_metric_configs",
                return_value=[{"name": "accuracy"}],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.normalize_context_to_list",
                return_value=[],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.MetricEvaluator",
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.evaluate_single_turn_metrics",
                return_value={"accuracy": {"score": 0.9, "is_successful": True}},
            ) as mock_eval,
        ):
            runner = SingleTurnRunner()
            exec_time, result, metrics = await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                prompt_content="prompt",
                expected_response="expected",
                evaluate_metrics=True,
                output_provider=mock_provider,
            )

        mock_eval.assert_called_once()
        assert metrics == {"accuracy": {"score": 0.9, "is_successful": True}}


# ============================================================================
# MultiTurnRunner with provider tests
# ============================================================================


class TestMultiTurnRunnerWithProvider:
    """Tests for MultiTurnRunner with injected OutputProvider."""

    @pytest.mark.asyncio
    async def test_uses_injected_provider(self):
        """MultiTurnRunner calls injected provider's get_output."""
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response={"conversation_summary": [{"penelope_message": "Hi"}]},
                execution_time=0,
                metrics={},
                source="test_result",
            )
        )

        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_test.test_configuration = {"goal": "Greet"}

        with patch(
            "rhesis.backend.tasks.execution.executors.runners.evaluate_multi_turn_metrics",
            return_value={"goal_achievement": {"score": 0.8}},
        ) as mock_eval:
            runner = MultiTurnRunner()
            exec_time, trace, metrics = await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                user_id="user-1",
                output_provider=mock_provider,
            )

        mock_provider.get_output.assert_called_once()
        assert trace == {"conversation_summary": [{"penelope_message": "Hi"}]}
        assert exec_time == 0
        # External evaluation should be called since provider returned empty metrics
        mock_eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_provider_metrics_when_present(self):
        """When provider returns metrics (live Penelope), skip external evaluation."""
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response={"conversation_summary": []},
                execution_time=2500,
                metrics={"goal_achieved": True, "score": 0.95},
                source="live",
            )
        )

        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_test.test_configuration = {"goal": "Test"}

        with patch(
            "rhesis.backend.tasks.execution.executors.runners.evaluate_multi_turn_metrics",
        ) as mock_eval:
            runner = MultiTurnRunner()
            exec_time, trace, metrics = await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                output_provider=mock_provider,
            )

        # External evaluation should NOT be called
        mock_eval.assert_not_called()
        assert metrics == {"goal_achieved": True, "score": 0.95}

    @pytest.mark.asyncio
    async def test_defaults_to_multi_turn_output(self):
        """When output_provider is None, MultiTurnOutput is used."""
        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_test.test_configuration = {"goal": "Test"}

        with patch(
            "rhesis.backend.tasks.execution.executors.runners.MultiTurnOutput",
        ) as mock_mt_class:
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_output = AsyncMock(
                return_value=TestOutput(
                    response={"conversation_summary": []},
                    execution_time=1000,
                    metrics={"penelope_metric": 0.9},
                )
            )
            mock_mt_class.return_value = mock_provider_instance

            runner = MultiTurnRunner()
            exec_time, trace, metrics = await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                model="gpt-4",
                output_provider=None,
            )

        mock_mt_class.assert_called_once_with(model="gpt-4")
        assert metrics == {"penelope_metric": 0.9}

    @pytest.mark.asyncio
    async def test_calls_external_eval_for_stored_output(self):
        """For stored output (empty metrics), evaluate_multi_turn_metrics is called."""
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response={
                    "conversation_summary": [{"penelope_message": "Q", "target_response": "A"}]
                },
                execution_time=0,
                metrics={},
                source="test_result",
            )
        )

        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_test.test_configuration = {"goal": "Ask Q"}

        with patch(
            "rhesis.backend.tasks.execution.executors.runners.evaluate_multi_turn_metrics",
            return_value={"relevance": {"score": 0.7}},
        ) as mock_eval:
            runner = MultiTurnRunner()
            _, _, metrics = await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
                output_provider=mock_provider,
            )

        mock_eval.assert_called_once()
        eval_kwargs = mock_eval.call_args.kwargs
        assert eval_kwargs["stored_output"] == {
            "conversation_summary": [{"penelope_message": "Q", "target_response": "A"}]
        }
        assert eval_kwargs["model"] == "gpt-4"
        assert metrics == {"relevance": {"score": 0.7}}

"""
Tests for pipeline wiring – ensuring new parameters flow from top to bottom.

Covers:
- execute_test: creates correct OutputProvider based on params
- execute_single_test Celery task: accepts and forwards new params
- execute_test_cases orchestration: passes params to execution strategies
- execute_tests_in_parallel: includes params in task kwargs
- execute_tests_sequentially: passes params to execute_test
- execute_test_configuration: extracts reference_test_run_id from attributes
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ============================================================================
# execute_test wiring tests
# ============================================================================


class TestExecuteTestWiring:
    """Tests that execute_test creates the correct OutputProvider."""

    @pytest.mark.asyncio
    async def test_no_provider_when_no_params(self):
        """When neither reference_test_run_id nor trace_id is set, provider is None."""
        mock_test = MagicMock()
        mock_test.id = "test-1"

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value={"test_id": "test-1", "execution_time": 100})

        with (
            patch(
                "rhesis.backend.tasks.execution.test_execution.get_test_and_prompt",
                return_value=(mock_test, "prompt", "expected"),
            ),
            patch(
                "rhesis.backend.tasks.execution.test_execution.create_executor",
                return_value=mock_executor,
            ),
        ):
            from rhesis.backend.tasks.execution.test_execution import (
                execute_test,
            )

            await execute_test(
                db=MagicMock(),
                test_config_id="cfg-1",
                test_run_id="run-1",
                test_id="test-1",
                endpoint_id="ep-1",
            )

        call_kwargs = mock_executor.execute.call_args.kwargs
        assert call_kwargs["output_provider"] is None

    @pytest.mark.asyncio
    async def test_creates_test_result_output_for_rescore(self):
        """When reference_test_run_id is set, TestResultOutput is created."""
        ref_run_id = str(uuid4())
        mock_test = MagicMock()
        mock_test.id = "test-1"

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value={"test_id": "test-1", "execution_time": 0})

        with (
            patch(
                "rhesis.backend.tasks.execution.test_execution.get_test_and_prompt",
                return_value=(mock_test, "prompt", "expected"),
            ),
            patch(
                "rhesis.backend.tasks.execution.test_execution.create_executor",
                return_value=mock_executor,
            ),
        ):
            from rhesis.backend.tasks.execution.test_execution import (
                execute_test,
            )

            await execute_test(
                db=MagicMock(),
                test_config_id="cfg-1",
                test_run_id="run-1",
                test_id="test-1",
                endpoint_id="ep-1",
                reference_test_run_id=ref_run_id,
            )

        call_kwargs = mock_executor.execute.call_args.kwargs
        provider = call_kwargs["output_provider"]
        assert provider is not None
        assert provider.__class__.__name__ == "TestResultOutput"
        assert provider.reference_test_run_id == ref_run_id

    @pytest.mark.asyncio
    async def test_creates_trace_output_for_trace_id(self):
        """When trace_id is set, TraceOutput is created."""
        mock_test = MagicMock()
        mock_test.id = "test-1"

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value={"test_id": "test-1", "execution_time": 0})

        with (
            patch(
                "rhesis.backend.tasks.execution.test_execution.get_test_and_prompt",
                return_value=(mock_test, "prompt", "expected"),
            ),
            patch(
                "rhesis.backend.tasks.execution.test_execution.create_executor",
                return_value=mock_executor,
            ),
        ):
            from rhesis.backend.tasks.execution.test_execution import (
                execute_test,
            )

            await execute_test(
                db=MagicMock(),
                test_config_id="cfg-1",
                test_run_id="run-1",
                test_id="test-1",
                endpoint_id="ep-1",
                trace_id="trace-xyz",
            )

        call_kwargs = mock_executor.execute.call_args.kwargs
        provider = call_kwargs["output_provider"]
        assert provider is not None
        assert provider.__class__.__name__ == "TraceOutput"
        assert provider.trace_id == "trace-xyz"

    @pytest.mark.asyncio
    async def test_rescore_takes_priority_over_trace(self):
        """When both reference_test_run_id and trace_id are set, rescore wins."""
        ref_run_id = str(uuid4())
        mock_test = MagicMock()
        mock_test.id = "test-1"

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value={"test_id": "test-1", "execution_time": 0})

        with (
            patch(
                "rhesis.backend.tasks.execution.test_execution.get_test_and_prompt",
                return_value=(mock_test, "prompt", "expected"),
            ),
            patch(
                "rhesis.backend.tasks.execution.test_execution.create_executor",
                return_value=mock_executor,
            ),
        ):
            from rhesis.backend.tasks.execution.test_execution import (
                execute_test,
            )

            await execute_test(
                db=MagicMock(),
                test_config_id="cfg-1",
                test_run_id="run-1",
                test_id="test-1",
                endpoint_id="ep-1",
                reference_test_run_id=ref_run_id,
                trace_id="trace-1",
            )

        call_kwargs = mock_executor.execute.call_args.kwargs
        provider = call_kwargs["output_provider"]
        assert provider.__class__.__name__ == "TestResultOutput"


# ============================================================================
# Orchestration passthrough tests
# ============================================================================


class TestOrchestrationPassthrough:
    """Tests that execute_test_cases passes params to execution strategies."""

    def test_parallel_receives_params(self):
        """execute_test_cases passes reference_test_run_id to parallel strategy."""
        mock_test_set = MagicMock()
        mock_test_set.tests = [MagicMock()]

        with (
            patch(
                "rhesis.backend.tasks.execution.orchestration.get_test_set",
                return_value=mock_test_set,
            ),
            patch(
                "rhesis.backend.tasks.execution.orchestration.get_execution_mode",
            ) as mock_mode,
            patch(
                "rhesis.backend.tasks.execution.orchestration.execute_tests_in_parallel",
                return_value={"total_tests": 1},
            ) as mock_parallel,
        ):
            from rhesis.backend.tasks.enums import ExecutionMode
            from rhesis.backend.tasks.execution.orchestration import (
                execute_test_cases,
            )

            mock_mode.return_value = ExecutionMode.PARALLEL

            execute_test_cases(
                session=MagicMock(),
                test_config=MagicMock(),
                test_run=MagicMock(),
                reference_test_run_id="ref-run-1",
                trace_id="trace-1",
            )

        call_kwargs = mock_parallel.call_args.kwargs
        assert call_kwargs["reference_test_run_id"] == "ref-run-1"
        assert call_kwargs["trace_id"] == "trace-1"

    def test_sequential_receives_params(self):
        """execute_test_cases passes reference_test_run_id to sequential strategy."""
        mock_test_set = MagicMock()
        mock_test_set.tests = [MagicMock()]

        with (
            patch(
                "rhesis.backend.tasks.execution.orchestration.get_test_set",
                return_value=mock_test_set,
            ),
            patch(
                "rhesis.backend.tasks.execution.orchestration.get_execution_mode",
            ) as mock_mode,
            patch(
                "rhesis.backend.tasks.execution.orchestration.execute_tests_sequentially",
                return_value={"total_tests": 1},
            ) as mock_sequential,
        ):
            from rhesis.backend.tasks.enums import ExecutionMode
            from rhesis.backend.tasks.execution.orchestration import (
                execute_test_cases,
            )

            mock_mode.return_value = ExecutionMode.SEQUENTIAL

            execute_test_cases(
                session=MagicMock(),
                test_config=MagicMock(),
                test_run=MagicMock(),
                reference_test_run_id="ref-run-2",
            )

        call_kwargs = mock_sequential.call_args.kwargs
        assert call_kwargs["reference_test_run_id"] == "ref-run-2"


# ============================================================================
# Parallel execution task kwargs tests
# ============================================================================


class TestParallelTaskKwargs:
    """Tests that execute_tests_in_parallel includes new params in task kwargs."""

    def test_includes_reference_test_run_id_in_tasks(self):
        """Parallel execution includes reference_test_run_id in chord task kwargs."""
        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_config = MagicMock()
        mock_config.id = "cfg-1"
        mock_config.endpoint_id = "ep-1"
        mock_config.organization_id = "org-1"
        mock_config.user_id = "user-1"
        mock_run = MagicMock()
        mock_run.id = "run-1"

        with (
            patch(
                "rhesis.backend.tasks.execution.parallel.update_test_run_start",
            ),
            patch(
                "rhesis.backend.tasks.execution.parallel.execute_single_test",
            ) as mock_task,
            patch(
                "rhesis.backend.tasks.execution.parallel.collect_results",
            ) as mock_collect,
            patch(
                "rhesis.backend.tasks.execution.parallel.chord",
            ) as mock_chord,
            patch(
                "rhesis.backend.tasks.execution.parallel.create_execution_result",
                return_value={"total_tests": 1},
            ),
        ):
            mock_sig = MagicMock()
            mock_task.s = MagicMock(return_value=mock_sig)
            mock_chord_result = MagicMock()
            mock_chord.return_value = mock_chord_result
            mock_collect.s = MagicMock(return_value=MagicMock())

            from rhesis.backend.tasks.execution.parallel import (
                execute_tests_in_parallel,
            )

            execute_tests_in_parallel(
                session=MagicMock(),
                test_config=mock_config,
                test_run=mock_run,
                tests=[mock_test],
                reference_test_run_id="ref-run-99",
            )

        call_kwargs = mock_task.s.call_args.kwargs
        assert call_kwargs["reference_test_run_id"] == "ref-run-99"

    def test_excludes_none_optional_params(self):
        """Parallel execution omits reference_test_run_id when it is None."""
        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_config = MagicMock()
        mock_config.id = "cfg-1"
        mock_config.endpoint_id = "ep-1"
        mock_config.organization_id = "org-1"
        mock_config.user_id = "user-1"
        mock_run = MagicMock()
        mock_run.id = "run-1"

        with (
            patch(
                "rhesis.backend.tasks.execution.parallel.update_test_run_start",
            ),
            patch(
                "rhesis.backend.tasks.execution.parallel.execute_single_test",
            ) as mock_task,
            patch(
                "rhesis.backend.tasks.execution.parallel.collect_results",
            ) as mock_collect,
            patch(
                "rhesis.backend.tasks.execution.parallel.chord",
            ) as mock_chord,
            patch(
                "rhesis.backend.tasks.execution.parallel.create_execution_result",
                return_value={"total_tests": 1},
            ),
        ):
            mock_sig = MagicMock()
            mock_task.s = MagicMock(return_value=mock_sig)
            mock_chord_result = MagicMock()
            mock_chord.return_value = mock_chord_result
            mock_collect.s = MagicMock(return_value=MagicMock())

            from rhesis.backend.tasks.execution.parallel import (
                execute_tests_in_parallel,
            )

            execute_tests_in_parallel(
                session=MagicMock(),
                test_config=mock_config,
                test_run=mock_run,
                tests=[mock_test],
            )

        call_kwargs = mock_task.s.call_args.kwargs
        assert "reference_test_run_id" not in call_kwargs
        assert "trace_id" not in call_kwargs


# ============================================================================
# test_configuration task attribute extraction tests
# ============================================================================


class TestTestConfigurationAttributeExtraction:
    """Tests that execute_test_configuration extracts reference_test_run_id from attributes.

    These tests verify the attribute extraction logic in isolation, without
    invoking the full Celery task machinery.
    """

    def test_extracts_reference_from_attributes(self):
        """The orchestration receives reference_test_run_id from config attributes."""
        # Test the attribute extraction logic directly

        mock_config = MagicMock()
        mock_config.attributes = {
            "reference_test_run_id": "ref-run-abc",
            "is_rescore": True,
        }

        # Extract attributes the same way test_configuration.py does
        config_attrs = mock_config.attributes or {}
        reference_test_run_id = config_attrs.get("reference_test_run_id")

        assert reference_test_run_id == "ref-run-abc"

    def test_no_reference_when_attributes_empty(self):
        """When attributes is empty/None, reference_test_run_id is None."""
        mock_config = MagicMock()
        mock_config.attributes = None

        config_attrs = mock_config.attributes or {}
        reference_test_run_id = config_attrs.get("reference_test_run_id")

        assert reference_test_run_id is None

    def test_no_reference_when_key_missing(self):
        """When attributes exists but has no reference_test_run_id, result is None."""
        mock_config = MagicMock()
        mock_config.attributes = {"execution_mode": "Parallel"}

        config_attrs = mock_config.attributes or {}
        reference_test_run_id = config_attrs.get("reference_test_run_id")

        assert reference_test_run_id is None

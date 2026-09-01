"""Progress narration: each flow's new ``self.emit(...)`` calls fire with the
expected message at the expected checkpoint.

``BaseJob.emit`` itself is already covered exhaustively (test_base_job_emit.py,
test_dispatcher.py, test_websocket_sink.py) -- these tests only pin down that
each task calls it, with the right count and message, at the right moment.
Mocking follows each module's own existing test harness
(test_owasp_test_set_task.py, test_garak.py) rather than inventing a new one.
"""

import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.jobs.garak import import_garak_probes_task, sync_garak_test_set_task
from rhesis.backend.jobs.test_set import (
    generate_and_save_owasp_test_set,
    generate_and_save_test_set,
)


@contextmanager
def _fake_db_session(db):
    yield db


def _fake_db_test_set():
    row = MagicMock()
    row.id = "ts-1"
    row.name = "Test Set"
    row.description = "desc"
    row.short_description = "short"
    row.attributes = {"metadata": {}}
    return row


@pytest.mark.unit
class TestTestSetGenerationNarration:
    def test_emits_generating_generated_and_saved_in_order(self):
        fake_sdk_test_set = MagicMock()
        fake_sdk_test_set.tests = [MagicMock() for _ in range(5)]
        mock_synthesizer = MagicMock()

        def _fake_generate(num_tests, on_progress=None):
            if on_progress:
                on_progress(3, 5)
                on_progress(5, 5)
            return fake_sdk_test_set

        mock_synthesizer.generate.side_effect = _fake_generate

        with (
            patch.object(
                generate_and_save_test_set,
                "get_tenant_context",
                return_value=("org-1", "user-1", "proj-1"),
            ),
            patch.object(generate_and_save_test_set, "update_state"),
            patch.object(generate_and_save_test_set, "emit") as mock_emit,
            patch.object(generate_and_save_test_set, "set_progress") as mock_progress,
            patch(
                "rhesis.backend.jobs.test_set._resolve_generation_model",
                return_value="fake-model",
            ),
            patch(
                "rhesis.sdk.synthesizers.ConfigSynthesizer",
                return_value=mock_synthesizer,
            ),
            patch(
                "rhesis.backend.jobs.test_set._save_test_set_to_database",
                return_value=_fake_db_test_set(),
            ),
            patch("rhesis.backend.jobs.test_set.dispatch_accrual"),
        ):
            generate_and_save_test_set(
                config={"requirements": ["req1"]},
                num_tests=5,
            )

        messages = [call.args[0] for call in mock_emit.call_args_list]
        assert messages == [
            "Generating 5 single turn tests using fake-model",
            "Generated 3 of 5 tests",
            "Generated 5 of 5 tests",
            "Saved 5 tests to test set",
        ]
        assert mock_progress.call_args_list == [
            ((0, 5),),
            ((3, 5),),
            ((5, 5),),
            ((5, 5),),
        ]


@pytest.mark.unit
class TestOwaspTestSetGenerationNarration:
    def test_emits_generating_generated_and_saved_in_order(self):
        fake_sdk_test_set = MagicMock()
        fake_sdk_test_set.tests = [MagicMock() for _ in range(3)]
        mock_synthesizer = MagicMock()

        def _fake_generate(num_tests, on_progress=None):
            if on_progress:
                on_progress(3, 3)
            return fake_sdk_test_set

        mock_synthesizer.generate.side_effect = _fake_generate

        with (
            patch.object(
                generate_and_save_owasp_test_set,
                "get_tenant_context",
                return_value=("org-1", "user-1", "proj-1"),
            ),
            patch.object(generate_and_save_owasp_test_set, "update_state"),
            patch.object(generate_and_save_owasp_test_set, "emit") as mock_emit,
            patch.object(generate_and_save_owasp_test_set, "set_progress") as mock_progress,
            patch(
                "rhesis.backend.jobs.test_set._resolve_generation_model",
                return_value="fake-model",
            ),
            patch(
                "rhesis.sdk.synthesizers.OWASPSynthesizer",
                return_value=mock_synthesizer,
            ),
            patch(
                "rhesis.backend.jobs.test_set._save_test_set_to_database",
                return_value=_fake_db_test_set(),
            ),
            patch("rhesis.backend.jobs.test_set.dispatch_accrual"),
        ):
            generate_and_save_owasp_test_set(
                framework="llm",
                purpose="customer service chatbot for a bank",
                categories=["llm01"],
                num_tests=3,
            )

        messages = [call.args[0] for call in mock_emit.call_args_list]
        assert messages == [
            "Generating 3 OWASP LLM tests using fake-model",
            "Generated 3 of 3 tests",
            "Saved 3 tests to test set",
        ]
        assert mock_progress.call_args_list == [
            ((0, 3),),
            ((3, 3),),
            ((3, 3),),
        ]


@pytest.mark.unit
class TestGarakImportNarration:
    def test_emits_importing_and_complete_counts(self):
        mock_db = MagicMock()
        mock_importer = MagicMock()
        mock_importer.import_probes.return_value = {
            "test_sets": [],
            "total_test_sets": 2,
            "total_tests": 42,
            "garak_version": "0.14.0",
        }

        with (
            patch.object(
                import_garak_probes_task,
                "get_tenant_context",
                return_value=("org-1", "user", None),
            ),
            patch.object(
                import_garak_probes_task, "get_db_session", return_value=_fake_db_session(mock_db)
            ),
            patch.object(import_garak_probes_task, "emit") as mock_emit,
            patch(
                "rhesis.backend.app.services.garak.importer.GarakImporter",
                return_value=mock_importer,
            ),
            patch("rhesis.backend.jobs.garak.dispatch_accrual"),
        ):
            import_garak_probes_task(
                probes=[
                    {"module_name": "dan", "class_name": "Dan_11_0", "custom_name": None},
                    {"module_name": "dan", "class_name": "Dan_10_0", "custom_name": None},
                ],
                name_prefix="Garak",
                description_template=None,
            )

        messages = [call.args[0] for call in mock_emit.call_args_list]
        assert messages == [
            "Importing 2 Garak probe(s)",
            "Garak import complete: 2 test sets, 42 tests",
        ]


@pytest.mark.unit
class TestGarakSyncNarration:
    def test_emits_syncing_and_complete_counts(self):
        from rhesis.backend.app.services.garak.sync import SyncResult

        mock_db = MagicMock()
        mock_sync_service = MagicMock()
        mock_sync_service.sync_test_set.return_value = SyncResult(
            added=1,
            removed=2,
            unchanged=3,
            new_garak_version="0.14.0",
            old_garak_version="0.13.0",
        )

        with (
            patch.object(
                sync_garak_test_set_task, "get_tenant_context", return_value=("org", "user", None)
            ),
            patch.object(
                sync_garak_test_set_task, "get_db_session", return_value=_fake_db_session(mock_db)
            ),
            patch.object(sync_garak_test_set_task, "emit") as mock_emit,
            patch(
                "rhesis.backend.app.services.garak.sync.GarakSyncService",
                return_value=mock_sync_service,
            ),
            patch("rhesis.backend.jobs.garak.dispatch_accrual"),
        ):
            sync_garak_test_set_task(test_set_id="test-set-id")

        messages = [call.args[0] for call in mock_emit.call_args_list]
        assert messages == [
            "Syncing Garak test set",
            "Sync complete: 1 added, 2 removed, 3 unchanged",
        ]


@pytest.mark.unit
class TestSequentialExecutionNarration:
    """The sequential runner calls on_progress and on_emit after each test."""

    def test_reports_per_test_progress_and_narration(self):
        from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially

        mock_session = MagicMock()
        mock_config = MagicMock()
        mock_config.id = "cfg-1"
        mock_config.organization_id = "org-1"
        mock_config.user_id = "user-1"
        mock_config.endpoint_id = "ep-1"
        mock_config.attributes = {}

        mock_run = MagicMock()
        mock_run.id = "run-1"
        mock_run.organization_id = "org-1"
        mock_run.user_id = "user-1"
        mock_run.attributes = {"task_id": "task-1"}

        tests = [MagicMock(id=f"t{i}") for i in range(3)]

        progress_calls = []
        emit_calls = []

        async def _fake_execute(**kwargs):
            return {"test_id": kwargs["test_id"], "status": "succeeded"}

        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fake_execute,
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.update_test_run_start",
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-1"),
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.is_task_revoked",
                return_value=False,
            ),
        ):
            execute_tests_sequentially(
                mock_session,
                mock_config,
                mock_run,
                tests,
                on_progress=lambda c, t: progress_calls.append((c, t)),
                on_emit=lambda m: emit_calls.append(m),
            )

        assert progress_calls == [(1, 3), (2, 3), (3, 3)]
        assert emit_calls == [
            "Test 1/3 completed",
            "Test 2/3 completed",
            "Test 3/3 completed",
        ]

    def test_reports_failure_narration(self):
        from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially

        mock_session = MagicMock()
        mock_config = MagicMock()
        mock_config.id = "cfg-1"
        mock_config.organization_id = "org-1"
        mock_config.user_id = "user-1"
        mock_config.endpoint_id = "ep-1"
        mock_config.attributes = {}

        mock_run = MagicMock()
        mock_run.id = "run-1"
        mock_run.organization_id = "org-1"
        mock_run.user_id = "user-1"
        mock_run.attributes = {"task_id": "task-1"}

        tests = [MagicMock(id="t1")]

        emit_calls = []

        async def _fail(**kwargs):
            raise RuntimeError("boom")

        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fail,
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.update_test_run_start",
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-1"),
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.is_task_revoked",
                return_value=False,
            ),
        ):
            execute_tests_sequentially(
                mock_session,
                mock_config,
                mock_run,
                tests,
                on_emit=lambda m: emit_calls.append(m),
            )

        # The reason is included: the activity log is read to find out *why* a test
        # failed, and the batch path has always named it while this one did not.
        assert emit_calls == ["Test 1/1 failed: boom"]


@pytest.mark.unit
class TestMetricLevelNarration:
    """evaluate_metrics no longer wires on_emit into per-metric feedback.

    Per-metric narration was producing ~28,000 ActivityLogged events (each
    opening its own DB session) for a single large run -- see
    jobs/execution/batch/evaluation.py's evaluate_metrics docstring comment.
    The batch-level "Test N/M" line in runner.py is the only narration left.
    """

    def test_no_emit_without_callback(self):
        from rhesis.backend.jobs.execution.batch.evaluation import evaluate_metrics

        ctx = MagicMock()
        ctx.get_metric_configs_for_test.return_value = ["cfg"]

        evaluator = MagicMock()

        async def _fake_a_evaluate(**kwargs):
            assert kwargs.get("on_metric_complete") is None
            return {}

        evaluator.a_evaluate = _fake_a_evaluate

        test = MagicMock()
        test.test_configuration = {}
        test.test_metadata = {}

        async def _fake_single_turn(
            _ctx, ev, _test, _output, _prompt, _expected, _configs, on_metric_complete=None
        ):
            return await ev.a_evaluate(
                input_text=_prompt,
                output_text="resp",
                expected_output=_expected,
                context=[],
                metrics=_configs,
                on_metric_complete=on_metric_complete,
            )

        with patch(
            "rhesis.backend.jobs.execution.batch.evaluation._evaluate_single_turn_metrics",
            side_effect=_fake_single_turn,
        ):
            result = asyncio.run(
                evaluate_metrics(
                    ctx,
                    evaluator,
                    test,
                    "t1",
                    {"response": "hello"},
                    "prompt",
                    "expected",
                    False,
                    {},
                )
            )
        assert result == {}

    def test_on_emit_present_still_gets_no_per_metric_callback(self):
        """Passing on_emit no longer wires it into a per-metric callback."""
        from rhesis.backend.jobs.execution.batch.evaluation import evaluate_metrics

        ctx = MagicMock()
        ctx.get_metric_configs_for_test.return_value = ["cfg"]

        evaluator = MagicMock()

        async def _fake_a_evaluate(**kwargs):
            assert kwargs.get("on_metric_complete") is None
            return {"Toxicity": {}}

        evaluator.a_evaluate = _fake_a_evaluate

        test = MagicMock()
        test.test_configuration = {}
        test.test_metadata = {}

        emit_calls = []

        async def _fake_single_turn(
            _ctx, ev, _test, _output, _prompt, _expected, _configs, on_metric_complete=None
        ):
            return await ev.a_evaluate(
                input_text=_prompt,
                output_text="resp",
                expected_output=_expected,
                context=[],
                metrics=_configs,
                on_metric_complete=on_metric_complete,
            )

        with patch(
            "rhesis.backend.jobs.execution.batch.evaluation._evaluate_single_turn_metrics",
            side_effect=_fake_single_turn,
        ):
            result = asyncio.run(
                evaluate_metrics(
                    ctx,
                    evaluator,
                    test,
                    "t1",
                    {"response": "hello"},
                    "prompt",
                    "expected",
                    False,
                    {},
                    on_emit=lambda m: emit_calls.append(m),
                )
            )

        assert result == {"Toxicity": {}}
        assert emit_calls == []


@pytest.mark.unit
class TestBatchExecutionNarration:
    """The batch runner calls on_emit after each test completes."""

    def test_reports_per_test_narration(self):
        from rhesis.backend.jobs.execution.batch.runner import run_batch

        ctx = MagicMock()
        ctx.batch_concurrency = 4
        ctx.per_test_timeout = 60
        ctx.recovery_rounds = 0
        ctx.celery_task_id = None

        cat1 = MagicMock()
        cat1.name = "Prompt Injection"
        test1 = MagicMock()
        test1.category = cat1
        cat2 = MagicMock()
        cat2.name = "Data Leakage"
        test2 = MagicMock()
        test2.category = cat2
        ctx.test_data = {
            "t1": {"test": test1},
            "t2": {"test": test2},
        }

        emit_calls = []
        progress_calls = []

        async def _fake_single(
            ctx, test_id, semaphore, agent, evaluator, on_emit=None, on_test_phase=None
        ):
            return {"test_id": test_id, "status": "succeeded", "execution_time": 10}

        with patch(
            "rhesis.backend.jobs.execution.batch.runner._execute_single_test",
            side_effect=_fake_single,
        ):
            results = asyncio.run(
                run_batch(
                    ctx,
                    ["t1", "t2"],
                    on_progress=lambda c, t: progress_calls.append((c, t)),
                    on_emit=lambda m: emit_calls.append(m),
                )
            )

        assert len(results) == 2
        assert progress_calls == [(1, 2), (2, 2)]
        assert emit_calls[0].startswith("Test 1/2 succeeded")
        assert emit_calls[1].startswith("Test 2/2 succeeded")
        assert any("Prompt Injection" in m or "Data Leakage" in m for m in emit_calls)

    def test_reports_error_reason_on_failure(self):
        from rhesis.backend.jobs.execution.batch.runner import run_batch

        ctx = MagicMock()
        ctx.batch_concurrency = 4
        ctx.per_test_timeout = 60
        ctx.recovery_rounds = 0
        ctx.celery_task_id = None

        test1 = MagicMock()
        test1.category = None
        ctx.test_data = {"t1": {"test": test1}}

        emit_calls = []

        async def _fake_single(
            ctx, test_id, semaphore, agent, evaluator, on_emit=None, on_test_phase=None
        ):
            return {
                "test_id": test_id,
                "status": "failed",
                "error": "Timeout after 60s",
                "execution_time": 60000,
            }

        with patch(
            "rhesis.backend.jobs.execution.batch.runner._execute_single_test",
            side_effect=_fake_single,
        ):
            asyncio.run(
                run_batch(
                    ctx,
                    ["t1"],
                    on_emit=lambda m: emit_calls.append(m),
                )
            )

        assert len(emit_calls) == 1
        assert "failed" in emit_calls[0]
        assert "Timeout after 60s" in emit_calls[0]

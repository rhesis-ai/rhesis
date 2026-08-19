"""Progress narration: each flow's new ``self.emit(...)`` calls fire with the
expected message at the expected checkpoint.

``BaseJob.emit`` itself is already covered exhaustively (test_base_job_emit.py,
test_dispatcher.py, test_websocket_sink.py) -- these tests only pin down that
each task calls it, with the right count and message, at the right moment.
Mocking follows each module's own existing test harness
(test_owasp_test_set_task.py, test_garak.py) rather than inventing a new one.
"""

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
        mock_synthesizer.generate.return_value = fake_sdk_test_set

        with (
            patch.object(
                generate_and_save_test_set,
                "get_tenant_context",
                return_value=("org-1", "user-1", "proj-1"),
            ),
            patch.object(generate_and_save_test_set, "update_state"),
            patch.object(generate_and_save_test_set, "emit") as mock_emit,
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
            "Generating 5 tests",
            "Generated 5 of 5 tests",
            "Saved 5 tests to test set",
        ]


@pytest.mark.unit
class TestOwaspTestSetGenerationNarration:
    def test_emits_generating_generated_and_saved_in_order(self):
        fake_sdk_test_set = MagicMock()
        fake_sdk_test_set.tests = [MagicMock() for _ in range(3)]
        mock_synthesizer = MagicMock()
        mock_synthesizer.generate.return_value = fake_sdk_test_set

        with (
            patch.object(
                generate_and_save_owasp_test_set,
                "get_tenant_context",
                return_value=("org-1", "user-1", "proj-1"),
            ),
            patch.object(generate_and_save_owasp_test_set, "update_state"),
            patch.object(generate_and_save_owasp_test_set, "emit") as mock_emit,
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
            "Generating 3 tests",
            "Generated 3 of 3 tests",
            "Saved 3 tests to test set",
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



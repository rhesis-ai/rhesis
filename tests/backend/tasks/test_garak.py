"""Unit tests for the Garak import/sync Celery tasks."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.services.garak.cache import serialize_probes_by_module
from rhesis.backend.app.services.garak.probes import GarakProbeInfo
from rhesis.backend.tasks.garak import import_garak_probes_task, sync_garak_test_set_task


@contextmanager
def _fake_db_session(db):
    yield db


@pytest.mark.unit
class TestImportGarakProbesTask:
    """Tests for import_garak_probes_task."""

    def test_calls_importer_with_preloaded_probes_and_tenant_context(self):
        mock_db = MagicMock()
        mock_importer = MagicMock()
        mock_importer.import_probes.return_value = {
            "test_sets": [],
            "total_test_sets": 0,
            "total_tests": 0,
            "garak_version": "0.14.0",
        }

        probes_by_module = {
            "dan": [
                GarakProbeInfo(
                    module_name="dan",
                    class_name="Dan_11_0",
                    full_name="dan.Dan_11_0",
                    description="d",
                )
            ]
        }

        with (
            patch.object(
                import_garak_probes_task, "get_tenant_context", return_value=("org", "user", None)
            ),
            patch.object(
                import_garak_probes_task, "get_db_session", return_value=_fake_db_session(mock_db)
            ),
            patch(
                "rhesis.backend.app.services.garak.importer.GarakImporter",
                return_value=mock_importer,
            ) as mock_importer_cls,
        ):
            result = import_garak_probes_task(
                probes=[{"module_name": "dan", "class_name": "Dan_11_0", "custom_name": None}],
                name_prefix="Garak",
                description_template=None,
                probes_by_module=serialize_probes_by_module(probes_by_module),
            )

        mock_importer_cls.assert_called_once_with(mock_db)
        mock_importer.preload_probes.assert_called_once()
        preloaded_arg = mock_importer.preload_probes.call_args[0][0]
        assert preloaded_arg["dan"][0].class_name == "Dan_11_0"

        mock_importer.import_probes.assert_called_once()
        call_kwargs = mock_importer.import_probes.call_args.kwargs
        assert call_kwargs["organization_id"] == "org"
        assert call_kwargs["user_id"] == "user"
        assert call_kwargs["name_prefix"] == "Garak"
        assert len(call_kwargs["probes"]) == 1
        assert call_kwargs["probes"][0].module_name == "dan"

        assert result["garak_version"] == "0.14.0"

    def test_stringifies_test_set_id_in_result(self):
        """test_set_id from the importer is a uuid.UUID — the task must coerce
        it to str so the Celery result is consistently JSON-native, matching
        what the old synchronous router response used to do."""
        mock_db = MagicMock()
        mock_importer = MagicMock()
        raw_uuid = uuid4()
        mock_importer.import_probes.return_value = {
            "test_sets": [
                {
                    "test_set_id": raw_uuid,
                    "test_set_name": "Garak: Dan 11 0",
                    "probe_full_name": "dan.Dan_11_0",
                    "test_count": 5,
                }
            ],
            "total_test_sets": 1,
            "total_tests": 5,
            "garak_version": "0.14.0",
        }

        with (
            patch.object(
                import_garak_probes_task, "get_tenant_context", return_value=("org", "user", None)
            ),
            patch.object(
                import_garak_probes_task, "get_db_session", return_value=_fake_db_session(mock_db)
            ),
            patch(
                "rhesis.backend.app.services.garak.importer.GarakImporter",
                return_value=mock_importer,
            ),
        ):
            result = import_garak_probes_task(
                probes=[{"module_name": "dan", "class_name": "Dan_11_0", "custom_name": None}],
                name_prefix="Garak",
                description_template=None,
                probes_by_module=None,
            )

        assert result["test_sets"][0]["test_set_id"] == str(raw_uuid)
        assert isinstance(result["test_sets"][0]["test_set_id"], str)

    def test_probes_by_module_none_skips_preload(self):
        """When the router found the cache cold it passes None — the task must
        skip preload_probes entirely so the importer falls back to its live
        per-probe extraction path instead of preloading an empty dict."""
        mock_db = MagicMock()
        mock_importer = MagicMock()
        mock_importer.import_probes.return_value = {
            "test_sets": [],
            "total_test_sets": 0,
            "total_tests": 0,
            "garak_version": "0.14.0",
        }

        with (
            patch.object(
                import_garak_probes_task, "get_tenant_context", return_value=("org", "user", None)
            ),
            patch.object(
                import_garak_probes_task, "get_db_session", return_value=_fake_db_session(mock_db)
            ),
            patch(
                "rhesis.backend.app.services.garak.importer.GarakImporter",
                return_value=mock_importer,
            ),
        ):
            import_garak_probes_task(
                probes=[{"module_name": "dan", "class_name": "Dan_11_0", "custom_name": None}],
                name_prefix="Garak",
                description_template=None,
                probes_by_module=None,
            )

        mock_importer.preload_probes.assert_not_called()


@pytest.mark.unit
class TestSyncGarakTestSetTask:
    """Tests for sync_garak_test_set_task."""

    def test_calls_sync_service_with_preloaded_probes_and_tenant_context(self):
        mock_db = MagicMock()
        mock_sync_service = MagicMock()

        from rhesis.backend.app.services.garak.sync import SyncResult

        mock_sync_service.sync_test_set.return_value = SyncResult(
            added=1,
            removed=0,
            unchanged=2,
            new_garak_version="0.14.0",
            old_garak_version="0.13.0",
        )

        probes_by_module = {
            "dan": [
                GarakProbeInfo(
                    module_name="dan",
                    class_name="Dan_11_0",
                    full_name="dan.Dan_11_0",
                    description="d",
                )
            ]
        }

        with (
            patch.object(
                sync_garak_test_set_task, "get_tenant_context", return_value=("org", "user", None)
            ),
            patch.object(
                sync_garak_test_set_task, "get_db_session", return_value=_fake_db_session(mock_db)
            ),
            patch(
                "rhesis.backend.app.services.garak.sync.GarakSyncService",
                return_value=mock_sync_service,
            ) as mock_sync_cls,
        ):
            result = sync_garak_test_set_task(
                test_set_id="test-set-id",
                probes_by_module=serialize_probes_by_module(probes_by_module),
            )

        mock_sync_cls.assert_called_once_with(mock_db)
        mock_sync_service.preload_probes.assert_called_once()
        mock_sync_service.sync_test_set.assert_called_once_with("test-set-id", "org", "user")

        assert result == {
            "added": 1,
            "removed": 0,
            "unchanged": 2,
            "new_garak_version": "0.14.0",
            "old_garak_version": "0.13.0",
        }

    def test_probes_by_module_none_skips_preload(self):
        """When the router found the cache cold it passes None — the task must
        skip preload_probes so the sync service falls back to its live
        extraction path instead of preloading an empty dict."""
        mock_db = MagicMock()
        mock_sync_service = MagicMock()

        from rhesis.backend.app.services.garak.sync import SyncResult

        mock_sync_service.sync_test_set.return_value = SyncResult(
            added=0,
            removed=0,
            unchanged=0,
            new_garak_version="0.14.0",
            old_garak_version="0.14.0",
        )

        with (
            patch.object(
                sync_garak_test_set_task, "get_tenant_context", return_value=("org", "user", None)
            ),
            patch.object(
                sync_garak_test_set_task, "get_db_session", return_value=_fake_db_session(mock_db)
            ),
            patch(
                "rhesis.backend.app.services.garak.sync.GarakSyncService",
                return_value=mock_sync_service,
            ),
        ):
            sync_garak_test_set_task(
                test_set_id="test-set-id",
                probes_by_module=None,
            )

        mock_sync_service.preload_probes.assert_not_called()

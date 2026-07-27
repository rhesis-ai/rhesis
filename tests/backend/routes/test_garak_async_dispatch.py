"""
Unit tests for the async-dispatch behavior of the Garak import/sync router
endpoints — calls the route handler coroutines directly (bypassing FastAPI's
dependency injection) with mocked dependencies, so no HTTP client/DB fixture
harness is needed. The underlying business logic (GarakImporter,
GarakSyncService, the Celery tasks themselves) is covered by dedicated unit
tests elsewhere; this file only verifies the router's dispatch wiring:
- import/sync launch the right Celery task via task_launcher and return 202
  task-response shapes
- import/sync pass only probe *identifiers* to the task (module/class or
  test_set_id) and never ship probe data (prompts) through the Celery broker —
  the task extracts the selected probes itself in the worker
- sync validates the target synchronously so a bad request gets a 400 rather
  than a background task that fails silently
- preview endpoints preload the (enumerating) probe cache before calling into
  the service
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.routers.garak import (
    import_probes,
    preview_import,
    preview_sync,
    sync_test_set,
)
from rhesis.backend.app.schemas.garak import GarakImportRequest, GarakProbeSelection
from rhesis.backend.app.services.garak.probes import GarakProbeInfo


def _mock_probe_service(probes_by_module):
    """Mock GarakProbeService. Only the preview endpoints use it now (via the
    enumerating cache read); import/sync dispatch no longer touch it."""
    service = MagicMock()
    service.enumerate_probe_modules_cached = AsyncMock(return_value=([], probes_by_module or {}))
    return service


@pytest.mark.unit
class TestImportProbesDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_import_task_and_returns_202_shape(self):
        request = GarakImportRequest(
            probes=[GarakProbeSelection(module_name="dan", class_name="Dan_11_0")],
            name_prefix="Garak",
        )
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())
        mock_db = MagicMock()

        with patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher:
            mock_launcher.return_value = MagicMock(id="task-abc-123")

            response = import_probes(
                request=request,
                db=mock_db,
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
            )

        mock_launcher.assert_called_once()
        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["db"] is mock_db
        assert call_kwargs["current_user"] is current_user
        # Only identifiers are dispatched — the requested (module, class) pairs
        # (GarakProbeSelection.model_dump also carries the optional custom_name).
        assert call_kwargs["probes"] == [
            {"module_name": "dan", "class_name": "Dan_11_0", "custom_name": None}
        ]
        assert "probes_by_module" not in call_kwargs

        assert response.task_id == "task-abc-123"
        assert response.probe_count == 1

    @pytest.mark.asyncio
    async def test_does_not_ship_probe_data_through_broker(self):
        """No probe payload (prompts) is serialized into the Celery dispatch —
        the task extracts the selected probes itself. A single "Full" probe
        would otherwise put thousands of prompts on the broker per dispatch."""
        request = GarakImportRequest(
            probes=[
                GarakProbeSelection(module_name="dan", class_name="Dan_11_0"),
                GarakProbeSelection(module_name="encoding", class_name="InjectBase64"),
            ],
            name_prefix="Garak",
        )
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())

        with patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher:
            mock_launcher.return_value = MagicMock(id="task-abc-123")

            import_probes(
                request=request,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
            )

        _, call_kwargs = mock_launcher.call_args
        assert "probes_by_module" not in call_kwargs
        assert call_kwargs["probes"] == [
            {"module_name": "dan", "class_name": "Dan_11_0", "custom_name": None},
            {"module_name": "encoding", "class_name": "InjectBase64", "custom_name": None},
        ]


@pytest.mark.unit
class TestSyncTestSetDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_sync_task_and_returns_202_shape(self):
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())
        test_set_id = str(uuid4())

        with (
            patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls,
            patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher,
        ):
            mock_sync_cls.return_value.resolve_sync_target.return_value = {"dan": ["Dan_11_0"]}
            mock_launcher.return_value = MagicMock(id="task-xyz-789")

            response = sync_test_set(
                test_set_id=test_set_id,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
            )

        # Target is resolved up front for validation, even though its result is
        # no longer used to filter a cache payload.
        mock_sync_cls.return_value.resolve_sync_target.assert_called_once()
        mock_launcher.assert_called_once()
        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["test_set_id"] == test_set_id
        assert "probes_by_module" not in call_kwargs

        assert response.task_id == "task-xyz-789"
        assert response.test_set_id == test_set_id

    @pytest.mark.asyncio
    async def test_returns_400_when_target_resolution_fails(self):
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())

        with patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls:
            mock_sync_cls.return_value.resolve_sync_target.side_effect = ValueError(
                "Test set not found: nope"
            )

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                sync_test_set(
                    test_set_id="nope",
                    db=MagicMock(),
                    tenant_context=(str(current_user.organization_id), str(current_user.id)),
                    current_user=current_user,
                )

        assert exc_info.value.status_code == 400


@pytest.mark.unit
class TestPreviewEndpointsPreloadCache:
    @pytest.mark.asyncio
    async def test_preview_import_preloads_probes_before_preview(self):
        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="d",
            prompt_count=5,
        )
        probe_service = _mock_probe_service({"dan": [probe]})
        request = GarakImportRequest(
            probes=[GarakProbeSelection(module_name="dan", class_name="Dan_11_0")],
            name_prefix="Garak",
        )

        with patch("rhesis.backend.app.routers.garak.GarakImporter") as mock_importer_cls:
            mock_importer = mock_importer_cls.return_value
            mock_importer.get_import_preview.return_value = {
                "garak_version": "0.14.0",
                "total_test_sets": 1,
                "total_tests": 5,
                "detector_count": 0,
                "detectors": [],
                "probes": [],
            }

            await preview_import(
                request=request,
                db=MagicMock(),
                tenant_context=(str(uuid4()), str(uuid4())),
                current_user=MagicMock(),
                probe_service=probe_service,
            )

        mock_importer.preload_probes.assert_called_once()
        preloaded = mock_importer.preload_probes.call_args[0][0]
        assert preloaded["dan"][0].class_name == "Dan_11_0"

    @pytest.mark.asyncio
    async def test_preview_sync_preloads_probes_before_preview(self):
        probe_service = _mock_probe_service({"dan": []})

        with patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls:
            mock_sync_service = mock_sync_cls.return_value
            mock_sync_service.get_sync_preview.return_value = {
                "can_sync": True,
                "old_version": "0.13.0",
                "new_version": "0.14.0",
                "to_add": 0,
                "to_remove": 0,
                "unchanged": 0,
                "last_synced_at": None,
            }

            await preview_sync(
                test_set_id=str(uuid4()),
                db=MagicMock(),
                tenant_context=(str(uuid4()), None),
                current_user=MagicMock(),
                probe_service=probe_service,
            )

        mock_sync_service.preload_probes.assert_called_once_with({"dan": []})

"""
Unit tests for the async-dispatch behavior of the Garak import/sync router
endpoints — calls the route handler coroutines directly (bypassing FastAPI's
dependency injection) with mocked dependencies, so no HTTP client/DB fixture
harness is needed. The underlying business logic (GarakImporter,
GarakSyncService, the Celery tasks themselves) is covered by dedicated unit
tests elsewhere; this file only verifies the router's dispatch wiring:
- import/sync launch the right Celery task via task_launcher and return 202
  task-response shapes
- import/sync read the probe cache via the non-enumerating get_cached_probes()
  (never triggering enumeration on a miss) and filter it down to exactly the
  probes/classes referenced by the request, passing None through when cold
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


def _mock_probe_service(cached_probes_by_module):
    """cached_probes_by_module=None simulates a cold cache."""
    service = MagicMock()
    service.get_cached_probes = AsyncMock(return_value=cached_probes_by_module)
    service.enumerate_probe_modules_cached = AsyncMock(
        return_value=([], cached_probes_by_module or {})
    )
    return service


@pytest.mark.unit
class TestImportProbesDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_import_task_and_returns_202_shape(self):
        probe = GarakProbeInfo(
            module_name="dan", class_name="Dan_11_0", full_name="dan.Dan_11_0", description="d"
        )
        probe_service = _mock_probe_service({"dan": [probe]})
        request = GarakImportRequest(
            probes=[GarakProbeSelection(module_name="dan", class_name="Dan_11_0")],
            name_prefix="Garak",
        )
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())
        mock_db = MagicMock()

        with patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher:
            mock_launcher.return_value = MagicMock(id="task-abc-123")

            response = await import_probes(
                request=request,
                db=mock_db,
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        mock_launcher.assert_called_once()
        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["db"] is mock_db
        assert call_kwargs["current_user"] is current_user
        assert call_kwargs["probes_by_module"]["dan"][0]["class_name"] == "Dan_11_0"

        assert response.task_id == "task-abc-123"
        assert response.probe_count == 1

    @pytest.mark.asyncio
    async def test_filters_probes_to_only_requested_classes(self):
        """Filtering must be exact-probe-class, not whole-module — a sibling
        probe in the same module (e.g. a "Full" variant with thousands of
        prompts) must not be serialized through the Celery dispatch."""
        dan_probe = GarakProbeInfo(
            module_name="dan", class_name="Dan_11_0", full_name="dan.Dan_11_0", description="d"
        )
        dan_full_probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0_Full",
            full_name="dan.Dan_11_0_Full",
            description="d",
        )
        encoding_probe = GarakProbeInfo(
            module_name="encoding",
            class_name="InjectBase64",
            full_name="encoding.InjectBase64",
            description="e",
        )
        probe_service = _mock_probe_service(
            {"dan": [dan_probe, dan_full_probe], "encoding": [encoding_probe]}
        )
        request = GarakImportRequest(
            probes=[GarakProbeSelection(module_name="dan", class_name="Dan_11_0")],
            name_prefix="Garak",
        )
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())

        with patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher:
            mock_launcher.return_value = MagicMock(id="task-abc-123")

            await import_probes(
                request=request,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        _, call_kwargs = mock_launcher.call_args
        filtered = call_kwargs["probes_by_module"]
        # Only "dan" module present, and only the requested Dan_11_0 class —
        # not the sibling Dan_11_0_Full, and not the unrelated "encoding" module.
        assert set(filtered.keys()) == {"dan"}
        assert [p["class_name"] for p in filtered["dan"]] == ["Dan_11_0"]

    @pytest.mark.asyncio
    async def test_cold_cache_dispatches_with_no_preload_data(self):
        """A cold cache must never trigger enumeration on the request thread —
        get_cached_probes() returning None means the router passes
        probes_by_module=None through so the task falls back to targeted
        live extraction inside the worker."""
        probe_service = _mock_probe_service(None)
        request = GarakImportRequest(
            probes=[GarakProbeSelection(module_name="dan", class_name="Dan_11_0")],
            name_prefix="Garak",
        )
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())

        with patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher:
            mock_launcher.return_value = MagicMock(id="task-abc-123")

            await import_probes(
                request=request,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["probes_by_module"] is None

    @pytest.mark.asyncio
    async def test_warm_cache_missing_a_requested_probe_falls_back_to_none(self):
        """Regression test: a warm cache that is MISSING one of the requested
        probes (e.g. a Garak version bump renamed/removed it) must not
        produce a partial preload dict — the importer would then silently
        skip the missing probe instead of falling back to live extraction. The
        whole request must fall back to probes_by_module=None instead."""
        dan_probe = GarakProbeInfo(
            module_name="dan", class_name="Dan_11_0", full_name="dan.Dan_11_0", description="d"
        )
        # Cache is warm and has "dan", but not the "encoding" probe requested below.
        probe_service = _mock_probe_service({"dan": [dan_probe]})
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

            await import_probes(
                request=request,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["probes_by_module"] is None


@pytest.mark.unit
class TestSyncTestSetDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_sync_task_and_returns_202_shape(self):
        probe = GarakProbeInfo(
            module_name="dan", class_name="Dan_11_0", full_name="dan.Dan_11_0", description="d"
        )
        probe_service = _mock_probe_service({"dan": [probe]})
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())
        test_set_id = str(uuid4())

        with (
            patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls,
            patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher,
        ):
            mock_sync_cls.return_value.resolve_sync_target.return_value = {"dan": ["Dan_11_0"]}
            mock_launcher.return_value = MagicMock(id="task-xyz-789")

            response = await sync_test_set(
                test_set_id=test_set_id,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        mock_launcher.assert_called_once()
        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["test_set_id"] == test_set_id
        assert call_kwargs["probes_by_module"]["dan"][0]["class_name"] == "Dan_11_0"

        assert response.task_id == "task-xyz-789"
        assert response.test_set_id == test_set_id

    @pytest.mark.asyncio
    async def test_legacy_target_includes_every_probe_in_each_module(self):
        """resolve_sync_target returning an empty class-name list for a module
        (the legacy sentinel) must include every probe in that module, not
        just the ones a naive single-class filter would keep."""
        dan_probe = GarakProbeInfo(
            module_name="dan", class_name="Dan_11_0", full_name="dan.Dan_11_0", description="d"
        )
        encoding_probe = GarakProbeInfo(
            module_name="encoding",
            class_name="InjectBase64",
            full_name="encoding.InjectBase64",
            description="e",
        )
        probe_service = _mock_probe_service({"dan": [dan_probe], "encoding": [encoding_probe]})
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())
        test_set_id = str(uuid4())

        with (
            patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls,
            patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher,
        ):
            mock_sync_cls.return_value.resolve_sync_target.return_value = {
                "dan": [],
                "encoding": [],
            }
            mock_launcher.return_value = MagicMock(id="task-xyz-789")

            await sync_test_set(
                test_set_id=test_set_id,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        _, call_kwargs = mock_launcher.call_args
        filtered = call_kwargs["probes_by_module"]
        assert [p["class_name"] for p in filtered["dan"]] == ["Dan_11_0"]
        assert [p["class_name"] for p in filtered["encoding"]] == ["InjectBase64"]

    @pytest.mark.asyncio
    async def test_cold_cache_dispatches_with_no_preload_data(self):
        probe_service = _mock_probe_service(None)
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())
        test_set_id = str(uuid4())

        with (
            patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls,
            patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher,
        ):
            mock_sync_cls.return_value.resolve_sync_target.return_value = {"dan": ["Dan_11_0"]}
            mock_launcher.return_value = MagicMock(id="task-xyz-789")

            await sync_test_set(
                test_set_id=test_set_id,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["probes_by_module"] is None

    @pytest.mark.asyncio
    async def test_warm_cache_missing_a_legacy_module_falls_back_to_none(self):
        """Critical regression test (flagged in PR review): a warm cache that
        is missing one of the legacy sync's target modules (e.g. a Garak
        version bump renamed/removed it) must NOT produce a partial preload
        dict with an empty list for that module. GarakSyncService's legacy
        sync path treats "zero probes for a listed module" as "every existing
        test in that module was removed upstream" and deletes them — so a
        partial preload here would silently wipe the test set instead of
        falling back to live extraction."""
        dan_probe = GarakProbeInfo(
            module_name="dan", class_name="Dan_11_0", full_name="dan.Dan_11_0", description="d"
        )
        # Cache is warm and has "dan", but the target also needs "encoding",
        # which is absent from this (warm) cache.
        probe_service = _mock_probe_service({"dan": [dan_probe]})
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())
        test_set_id = str(uuid4())

        with (
            patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls,
            patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher,
        ):
            mock_sync_cls.return_value.resolve_sync_target.return_value = {
                "dan": [],
                "encoding": [],
            }
            mock_launcher.return_value = MagicMock(id="task-xyz-789")

            await sync_test_set(
                test_set_id=test_set_id,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["probes_by_module"] is None

    @pytest.mark.asyncio
    async def test_warm_cache_missing_the_target_probe_class_falls_back_to_none(self):
        """Same regression, modern single-probe format: the cache has the
        module but not the specific probe class the test set references."""
        dan_probe = GarakProbeInfo(
            module_name="dan", class_name="Dan_10_0", full_name="dan.Dan_10_0", description="d"
        )
        probe_service = _mock_probe_service({"dan": [dan_probe]})
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())
        test_set_id = str(uuid4())

        with (
            patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls,
            patch("rhesis.backend.app.routers.garak.task_launcher") as mock_launcher,
        ):
            mock_sync_cls.return_value.resolve_sync_target.return_value = {"dan": ["Dan_11_0"]}
            mock_launcher.return_value = MagicMock(id="task-xyz-789")

            await sync_test_set(
                test_set_id=test_set_id,
                db=MagicMock(),
                tenant_context=(str(current_user.organization_id), str(current_user.id)),
                current_user=current_user,
                probe_service=probe_service,
            )

        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["probes_by_module"] is None

    @pytest.mark.asyncio
    async def test_returns_400_when_target_resolution_fails(self):
        current_user = MagicMock(id=uuid4(), organization_id=uuid4())

        with patch("rhesis.backend.app.routers.garak.GarakSyncService") as mock_sync_cls:
            mock_sync_cls.return_value.resolve_sync_target.side_effect = ValueError(
                "Test set not found: nope"
            )

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await sync_test_set(
                    test_set_id="nope",
                    db=MagicMock(),
                    tenant_context=(str(current_user.organization_id), str(current_user.id)),
                    current_user=current_user,
                    probe_service=_mock_probe_service({}),
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

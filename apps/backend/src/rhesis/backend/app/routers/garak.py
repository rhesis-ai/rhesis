"""
Garak integration API router.

Provides endpoints for listing, importing, syncing, and dynamically generating
test sets from Garak probes as Rhesis test sets.
"""

import logging
import random

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.garak import (
    GarakGenerateRequest,
    GarakGenerateResponse,
    GarakImportPreviewResponse,
    GarakImportRequest,
    GarakImportTaskResponse,
    GarakProbeClassResponse,
    GarakProbeDetailResponse,
    GarakProbeModuleResponse,
    GarakProbePreview,
    GarakProbesListResponse,
    GarakSyncPreviewResponse,
    GarakSyncTaskResponse,
)
from rhesis.backend.app.services.garak import (
    GarakDynamicGenerator,
    GarakImporter,
    GarakProbeService,
    GarakSyncService,
    GarakTaxonomy,
)
from rhesis.backend.app.services.garak.taxonomy import resolve_behavior
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.garak import import_garak_probes_task, sync_garak_test_set_task
from rhesis.backend.tasks.test_set import generate_and_save_test_set

logger = logging.getLogger(__name__)

router = RhesisRouter(
    prefix="/garak",
    tags=["garak"],
    responses={404: {"description": "Not found"}},
    resource="garak",
)


def get_probe_service() -> GarakProbeService:
    """FastAPI dependency that provides a per-request GarakProbeService instance.

    Using a dependency ensures the instance-level caches (_probe_cache,
    _probe_info_cache) are shared across all method calls within a single request,
    eliminating redundant module imports and re-enumeration.
    """
    return GarakProbeService()


@router.get("/probes", response_model=GarakProbesListResponse)
async def list_probe_modules(
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
):
    """
    List all available Garak probe modules with their probe classes.

    Returns a list of probe modules with their metadata, taxonomy mapping,
    and individual probe class details.

    Uses Redis caching to avoid re-enumerating probes on every request.
    The cache is pre-warmed on application startup.
    """
    try:
        # Use cached enumeration - checks L1 memory cache, then L2 Redis cache,
        # and only generates probe data on cache miss
        modules, probes_by_module = await probe_service.enumerate_probe_modules_cached()

        module_responses = []
        for module in modules:
            mapping = GarakTaxonomy.get_mapping(module.name)

            # Get probes from cached data
            probes = probes_by_module.get(module.name, [])
            probe_responses = [
                GarakProbeClassResponse(
                    class_name=p.class_name,
                    full_name=p.full_name,
                    module_name=p.module_name,
                    description=p.description,
                    prompt_count=p.prompt_count,
                    tags=p.tags,
                    detector=p.detector,
                    is_dynamic=p.is_dynamic,
                )
                for p in probes
            ]

            module_responses.append(
                GarakProbeModuleResponse(
                    name=module.name,
                    description=module.description,
                    probe_count=module.probe_count,
                    total_prompt_count=module.total_prompt_count,
                    tags=module.tags,
                    default_detector=module.default_detector,
                    rhesis_category=mapping.category,
                    rhesis_topic=mapping.topic,
                    rhesis_behavior=resolve_behavior(module.tags),
                    has_dynamic_probes=module.has_dynamic_probes,
                    probes=probe_responses,
                )
            )

        return GarakProbesListResponse(
            garak_version=probe_service.garak_version,
            modules=module_responses,
            total_modules=len(module_responses),
        )

    except RuntimeError as e:
        logger.error(f"Garak not available: {e}")
        raise HTTPException(
            status_code=503,
            detail="Garak package is not installed or not available",
        )
    except Exception as e:
        logger.error(f"Error listing Garak probes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list Garak probes: {str(e)}",
        )


@router.get("/probes/{module_name}", response_model=GarakProbeDetailResponse)
async def get_probe_module_detail(
    module_name: str,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
):
    """
    Get detailed information about a specific Garak probe module.

    Returns the probe classes, prompts, and metadata for the module.
    """
    try:
        module_info = probe_service.get_probe_details(module_name)

        if not module_info:
            raise HTTPException(
                status_code=404,
                detail=f"Probe module '{module_name}' not found",
            )

        # Get detailed probe information
        probes = probe_service.extract_probes_from_module(module_name)
        mapping = GarakTaxonomy.get_mapping(module_name)

        probe_details = [
            {
                "class_name": p.class_name,
                "full_name": p.full_name,
                "description": p.description,
                "tags": p.tags,
                "prompt_count": p.prompt_count,
                "detector": p.detector,
            }
            for p in probes
        ]

        return GarakProbeDetailResponse(
            name=module_info.name,
            description=module_info.description,
            probe_classes=module_info.probe_classes,
            probe_count=module_info.probe_count,
            total_prompt_count=module_info.total_prompt_count,
            tags=module_info.tags,
            default_detector=module_info.default_detector,
            rhesis_mapping={
                "category": mapping.category,
                "topic": mapping.topic,
                "behavior": resolve_behavior(module_info.tags),
            },
            probes=probe_details,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting probe module detail: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get probe module detail: {str(e)}",
        )


@router.post("/import/preview", response_model=GarakImportPreviewResponse)
async def preview_import(
    request: GarakImportRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
):
    """
    Preview what will be imported without creating test sets.

    Returns details of test sets that would be created for each probe.
    """
    try:
        # Preload from the Garak probe cache instead of re-instantiating each
        # selected probe from scratch — turns this into a Redis GET + dict
        # lookups rather than re-running probe extraction.
        _, probes_by_module = await probe_service.enumerate_probe_modules_cached()

        importer = GarakImporter(db)
        importer.preload_probes(probes_by_module)
        preview = importer.get_import_preview(
            probes=request.probes,
            name_prefix=request.name_prefix,
        )

        probe_previews = [
            GarakProbePreview(
                module_name=p["module_name"],
                class_name=p["class_name"],
                full_name=p["full_name"],
                test_set_name=p["test_set_name"],
                prompt_count=p["prompt_count"],
                detector=p.get("detector"),
            )
            for p in preview["probes"]
        ]

        return GarakImportPreviewResponse(
            garak_version=preview["garak_version"],
            total_test_sets=preview["total_test_sets"],
            total_tests=preview["total_tests"],
            detector_count=preview["detector_count"],
            detectors=preview["detectors"],
            probes=probe_previews,
        )

    except Exception as e:
        logger.error(f"Error previewing import: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to preview import: {str(e)}",
        )


@router.post("/import", response_model=GarakImportTaskResponse, status_code=202)
async def import_probes(
    request: GarakImportRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Import selected Garak probes as Rhesis test sets.

    Creates one test set per probe, with tests for each prompt, and associates
    appropriate Garak detector metrics. Some Garak probes produce thousands of
    prompts, so this runs as a background task rather than blocking the
    request — returns HTTP 202 Accepted with a `task_id` that can be polled
    via `GET /jobs/{task_id}`.
    """
    try:
        # Dispatch only the probe identifiers — the task extracts the selected
        # probes itself in the background. We deliberately do NOT ship probe
        # data (prompts) through the Celery broker: a single "Full" probe
        # carries thousands of prompts, so a multi-probe import would push
        # megabytes through the broker on one dispatch. Per-probe extraction in
        # the worker is bounded to the selected classes and dwarfed by the
        # test/prompt row writes the import does anyway. (The synchronous
        # preview endpoints still reuse the warm cache — there blocking the
        # request thread on enumeration is what we must avoid.)
        task_result = task_launcher(
            import_garak_probes_task,
            current_user=current_user,
            db=db,
            probes=[p.model_dump() for p in request.probes],
            name_prefix=request.name_prefix,
            description_template=request.description_template,
        )

        return GarakImportTaskResponse(
            task_id=str(task_result.id),
            probe_count=len(request.probes),
            message=f"Import started for {len(request.probes)} probe(s).",
        )

    except Exception as e:
        logger.error(f"Error launching Garak probe import: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to launch Garak probe import: {str(e)}",
        )


@router.get("/sync/{test_set_id}/preview", response_model=GarakSyncPreviewResponse)
async def preview_sync(
    test_set_id: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
):
    """
    Preview what changes would occur when syncing a test set.

    Returns counts of tests to add, remove, and keep.
    """
    try:
        organization_id, _ = tenant_context

        # Preload from the Garak probe cache instead of re-instantiating the
        # probe(s) from scratch.
        _, probes_by_module = await probe_service.enumerate_probe_modules_cached()

        sync_service = GarakSyncService(db)
        sync_service.preload_probes(probes_by_module)
        preview = sync_service.get_sync_preview(test_set_id, organization_id)

        if not preview:
            raise HTTPException(
                status_code=404,
                detail="Test set not found or is not a Garak-imported test set",
            )

        return GarakSyncPreviewResponse(**preview)

    except ValueError as e:
        logger.warning(f"Sync preview validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing sync: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to preview sync: {str(e)}",
        )


@router.post("/sync/{test_set_id}", response_model=GarakSyncTaskResponse, status_code=202)
async def sync_test_set(
    test_set_id: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Sync a Garak-imported test set with the latest probes.

    Updates the test set to include new probes and remove deprecated ones.
    Some Garak probes produce thousands of prompts, so this runs as a
    background task rather than blocking the request — returns HTTP 202
    Accepted with a `task_id` that can be polled via `GET /jobs/{task_id}`.
    """
    try:
        organization_id, _ = tenant_context

        sync_service = GarakSyncService(db)
        # Validate the test set is syncable up front so an invalid request
        # gets a synchronous 400 (via the ValueError handler below) instead of
        # a background task that fails silently. This is a cheap metadata read
        # — no probe extraction. The task re-resolves and extracts the probes
        # itself in the background; we deliberately don't ship probe data
        # (prompts) through the Celery broker (see import_probes for why).
        sync_service.resolve_sync_target(test_set_id, organization_id)

        task_result = task_launcher(
            sync_garak_test_set_task,
            current_user=current_user,
            db=db,
            test_set_id=test_set_id,
        )

        return GarakSyncTaskResponse(
            task_id=str(task_result.id),
            test_set_id=test_set_id,
            message=f"Sync started for test set {test_set_id}.",
        )

    except ValueError as e:
        logger.warning(f"Sync validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error launching test set sync: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to launch test set sync: {str(e)}",
        )


@router.post("/generate", response_model=GarakGenerateResponse, status_code=202)
async def generate_dynamic_probe(
    request: GarakGenerateRequest,
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
    db: Session = Depends(get_tenant_db_session),
):
    """
    Generate a test set from a **dynamic** Garak probe using the user's LLM.

    Dynamic probes have no static prompts — they generate them at runtime via RL
    agents, NLTK, or external ML models (e.g. `atkgen.Tox`, `fitd.FITD`,
    `topic.WordNet`).  This endpoint uses the probe's `goal`, `description`, and
    garak tags (OWASP LLM Top 10, AVID) to build a generation prompt for the
    user's configured LLM and launches an async task to produce and save the test
    set. All garak metadata is preserved on the resulting test set.

    Returns HTTP 202 Accepted with a `task_id` that can be polled via
    `GET /jobs/{task_id}`.
    """
    module_name = request.module_name
    class_name = request.class_name

    try:
        probes = probe_service.extract_probes_from_module(module_name, [class_name])

        if not probes:
            raise HTTPException(
                status_code=404,
                detail=f"Probe '{module_name}.{class_name}' not found",
            )

        probe_info = probes[0]

        if not probe_info.is_dynamic:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Probe '{module_name}.{class_name}' is not dynamic — "
                    "use POST /garak/import to import its static prompts instead."
                ),
            )

        generator = GarakDynamicGenerator()
        config, probe_metadata = generator.build(probe_info)

        # Choose a random test count in [100, 200] if the caller did not specify one
        num_tests = request.num_tests if request.num_tests is not None else random.randint(100, 200)

        test_set_name = request.name or f"Garak Dynamic: {probe_info.full_name}"

        task_result = task_launcher(
            generate_and_save_test_set,
            current_user=current_user,
            db=db,
            config=config.model_dump(),
            num_tests=num_tests,
            name=test_set_name,
            metadata=probe_metadata,
        )

        logger.info(
            "Garak dynamic generation task launched",
            extra={
                "task_id": task_result.id,
                "probe": probe_info.full_name,
                "num_tests": num_tests,
                "user_id": current_user.id,
                "organization_id": current_user.organization_id,
            },
        )

        return GarakGenerateResponse(
            task_id=str(task_result.id),
            probe_full_name=probe_info.full_name,
            num_tests=num_tests,
            message=(
                f"Dynamic test set generation started for '{probe_info.full_name}'. "
                f"Generating {num_tests} tests using your configured LLM."
            ),
        )

    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"Garak not available: {e}")
        raise HTTPException(
            status_code=503,
            detail="Garak package is not installed or not available",
        )
    except Exception as e:
        logger.error(f"Error launching dynamic generation for {module_name}.{class_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to launch dynamic probe generation: {str(e)}",
        )

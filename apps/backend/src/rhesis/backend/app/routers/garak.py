"""
Garak integration API router.

Provides endpoints for listing, importing, syncing, and dynamically generating
test sets from Garak probes as Rhesis test sets.
"""

import logging
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.garak import (
    GarakGenerateRequest,
    GarakGenerateResponse,
    GarakImportedTestSet,
    GarakImportPreviewResponse,
    GarakImportRequest,
    GarakImportResponse,
    GarakProbeClassResponse,
    GarakProbeDetailResponse,
    GarakProbeModuleResponse,
    GarakProbePreview,
    GarakProbesListResponse,
    GarakSyncPreviewResponse,
    GarakSyncResponse,
)
from rhesis.backend.app.services.garak import (
    GarakDynamicGenerator,
    GarakImporter,
    GarakProbeService,
    GarakSyncService,
    GarakTaxonomy,
)
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.test_set import generate_and_save_test_set

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/garak",
    tags=["garak"],
    responses={404: {"description": "Not found"}},
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
                    rhesis_behavior=mapping.behavior,
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
                "behavior": mapping.behavior,
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
):
    """
    Preview what will be imported without creating test sets.

    Returns details of test sets that would be created for each probe.
    """
    try:
        importer = GarakImporter(db)
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


@router.post("/import", response_model=GarakImportResponse)
async def import_probes(
    request: GarakImportRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Import selected Garak probes as Rhesis test sets.

    Creates one test set per probe, with tests for each prompt,
    and associates appropriate Garak detector metrics.
    """
    try:
        organization_id, user_id = tenant_context

        importer = GarakImporter(db)
        results = importer.import_probes(
            probes=request.probes,
            name_prefix=request.name_prefix,
            description_template=request.description_template,
            organization_id=organization_id,
            user_id=user_id,
        )

        test_set_responses = [
            GarakImportedTestSet(
                test_set_id=str(r["test_set_id"]),
                test_set_name=r["test_set_name"],
                probe_full_name=r["probe_full_name"],
                test_count=r["test_count"],
            )
            for r in results["test_sets"]
        ]

        return GarakImportResponse(
            test_sets=test_set_responses,
            total_test_sets=results["total_test_sets"],
            total_tests=results["total_tests"],
            garak_version=results["garak_version"],
        )

    except ValueError as e:
        logger.warning(f"Import validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error importing Garak probes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import Garak probes: {str(e)}",
        )


@router.get("/sync/{test_set_id}/preview", response_model=GarakSyncPreviewResponse)
async def preview_sync(
    test_set_id: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Preview what changes would occur when syncing a test set.

    Returns counts of tests to add, remove, and keep.
    """
    try:
        organization_id, _ = tenant_context

        sync_service = GarakSyncService(db)
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


@router.post("/sync/{test_set_id}", response_model=GarakSyncResponse)
async def sync_test_set(
    test_set_id: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Sync a Garak-imported test set with the latest probes.

    Updates the test set to include new probes and remove
    deprecated ones.
    """
    try:
        organization_id, user_id = tenant_context

        sync_service = GarakSyncService(db)
        result = sync_service.sync_test_set(
            test_set_id=test_set_id,
            organization_id=organization_id,
            user_id=user_id,
        )

        return GarakSyncResponse(
            added=result.added,
            removed=result.removed,
            unchanged=result.unchanged,
            new_garak_version=result.new_garak_version,
            old_garak_version=result.old_garak_version,
        )

    except ValueError as e:
        logger.warning(f"Sync validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing test set: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync test set: {str(e)}",
        )


@router.post("/generate", response_model=GarakGenerateResponse, status_code=202)
async def generate_dynamic_probe(
    request: GarakGenerateRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
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
    `GET /tasks/{task_id}`.
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

"""
Garak integration API router.

Provides endpoints for listing, importing, and syncing Garak probes
as Rhesis test sets.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.garak import (
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
    GarakImporter,
    GarakProbeService,
    GarakSyncService,
    GarakTaxonomy,
)
from rhesis.backend.logging.rhesis_logger import logger

router = APIRouter(
    prefix="/garak",
    tags=["garak"],
    responses={404: {"description": "Not found"}},
)


@router.get("/probes", response_model=GarakProbesListResponse)
async def list_probe_modules(
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    List all available Garak probe modules with their probe classes.

    Returns a list of probe modules with their metadata, taxonomy mapping,
    and individual probe class details.
    """
    try:
        probe_service = GarakProbeService()
        modules = probe_service.enumerate_probe_modules()

        module_responses = []
        for module in modules:
            mapping = GarakTaxonomy.get_mapping(module.name)

            # Get individual probe details
            probes = probe_service.extract_probes_from_module(module.name)
            probe_responses = [
                GarakProbeClassResponse(
                    class_name=p.class_name,
                    full_name=p.full_name,
                    module_name=p.module_name,
                    description=p.description,
                    prompt_count=p.prompt_count,
                    tags=p.tags,
                    detector=p.detector,
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
):
    """
    Get detailed information about a specific Garak probe module.

    Returns the probe classes, prompts, and metadata for the module.
    """
    try:
        probe_service = GarakProbeService()
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

"""
Garak integration API router.

Provides endpoints for listing, importing, syncing, and dynamically generating
test sets from Garak probes as Rhesis test sets.
"""

import logging
import random
from functools import partial
from typing import Optional

import anyio
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.quota_gates import require_job_capacity, require_quota
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    OffLoopSession,
    get_off_loop_tenant_session,
    get_tenant_context,
    get_tenant_db_session,
    per_user_rate_limit,
)
from rhesis.backend.app.error_handlers import PublicHTTPException
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import check_quota
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
from rhesis.backend.app.services.garak.taxonomy import resolve_requirement
from rhesis.backend.app.utils.rate_limit import GENERATION_RATE_LIMIT
from rhesis.backend.jobs import launch_reserved_job
from rhesis.backend.jobs.garak import import_garak_probes_task, sync_garak_test_set_task
from rhesis.backend.jobs.test_set import generate_and_save_test_set

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


#: Deliberate, secret-free text: names the one thing an operator can act on, so
#: it is raised as a PublicHTTPException and reaches the caller unmasked.
_GARAK_UNAVAILABLE = "Garak package is not installed or not available"


def _require_garak(probe_service: GarakProbeService) -> None:
    """Reject the request with a readable 503 when garak is not installed.

    For endpoints that only read a single module: the service swallows the
    ImportError there and returns nothing, which would otherwise surface as a
    misleading 404.
    """
    if probe_service.garak_version == "not_installed":
        raise PublicHTTPException(status_code=503, detail=_GARAK_UNAVAILABLE)


async def _enumerate_probes(probe_service: GarakProbeService):
    """Enumerate probe modules (cached), reporting a missing garak as a 503.

    The only call in this router that surfaces the service's
    RuntimeError for a missing garak package.
    """
    try:
        return await probe_service.enumerate_probe_modules_cached()
    except RuntimeError as e:
        raise PublicHTTPException(status_code=503, detail=_GARAK_UNAVAILABLE) from e


# The session is never used below -- probe enumeration is served from cache -- but the
# dependency stays: it is what binds usage attribution and validates X-Project-Id for
# this request.
@router.get(
    "/probes",
    response_model=GarakProbesListResponse,
    dependencies=[Depends(get_off_loop_tenant_session)],
)
async def list_probe_modules(
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
    # Use cached enumeration - checks L1 memory cache, then L2 Redis cache,
    # and only generates probe data on cache miss
    modules, probes_by_module = await _enumerate_probes(probe_service)

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
                rhesis_requirement=resolve_requirement(module.tags),
                has_dynamic_probes=module.has_dynamic_probes,
                probes=probe_responses,
            )
        )

    return GarakProbesListResponse(
        garak_version=probe_service.garak_version,
        modules=module_responses,
        total_modules=len(module_responses),
    )


@router.get("/probes/{module_name}", response_model=GarakProbeDetailResponse)
def get_probe_module_detail(
    module_name: str,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
):
    """
    Get detailed information about a specific Garak probe module.

    Returns the probe classes, prompts, and metadata for the module.
    """
    _require_garak(probe_service)

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
            "requirement": resolve_requirement(module_info.tags),
        },
        probes=probe_details,
    )


def _build_import_preview(
    db: Session,
    probes_by_module: dict,
    probes: list,
    name_prefix: str | None,
) -> dict:
    """Run the importer's preview against the database, off the event loop."""
    importer = GarakImporter(db)
    importer.preload_probes(probes_by_module)
    return importer.get_import_preview(probes=probes, name_prefix=name_prefix)


@router.post("/import/preview", response_model=GarakImportPreviewResponse)
async def preview_import(
    request: GarakImportRequest,
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
):
    """
    Preview what will be imported without creating test sets.

    Returns details of test sets that would be created for each probe.
    """
    # Preload from the Garak probe cache instead of re-instantiating each
    # selected probe from scratch — turns this into a Redis GET + dict
    # lookups rather than re-running probe extraction.
    _, probes_by_module = await _enumerate_probes(probe_service)

    preview = await anyio.to_thread.run_sync(
        _build_import_preview,
        db,
        probes_by_module,
        request.probes,
        request.name_prefix,
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


@router.post(
    "/import",
    response_model=GarakImportTaskResponse,
    status_code=202,
    dependencies=[per_user_rate_limit(GENERATION_RATE_LIMIT)],
)
async def import_probes(
    request: GarakImportRequest,
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
    _quota_gate: Organization = Depends(require_quota(QuotaResource.TEST_GENERATION)),
    _job_capacity: None = Depends(require_job_capacity),
):
    """
    Import selected Garak probes as Rhesis test sets.

    Creates one test set per probe, with tests for each prompt, and associates
    appropriate Garak detector metrics. Some Garak probes produce thousands of
    prompts, so this runs as a background task rather than blocking the
    request — returns HTTP 202 Accepted with a `task_id` that can be polled
    via `GET /jobs/by-celery-id/{task_id}`.
    """
    # Dispatch only the probe identifiers — the task extracts the selected
    # probes itself in the background. We deliberately do NOT ship probe
    # data (prompts) through the Celery broker: a single "Full" probe
    # carries thousands of prompts, so a multi-probe import would push
    # megabytes through the broker on one dispatch. The warm cache only
    # supplies the prompt counts the import will create, to reserve them.
    _, probes_by_module = await _enumerate_probes(probe_service)
    amount = _selected_prompt_count(probes_by_module, request.probes)
    if amount is None:
        raise HTTPException(status_code=400, detail="Some selected probes are not available")

    task_result = await anyio.to_thread.run_sync(
        partial(
            launch_reserved_job,
            import_garak_probes_task,
            org=_quota_gate,
            resource=QuotaResource.TEST_GENERATION,
            amount=amount,
            current_user=current_user,
            db=db,
            probes=[p.model_dump() for p in request.probes],
            name_prefix=request.name_prefix,
            description_template=request.description_template,
        )
    )

    return GarakImportTaskResponse(
        task_id=str(task_result.id),
        probe_count=len(request.probes),
        message=f"Import started for {len(request.probes)} probe(s).",
    )


def _selected_prompt_count(probes_by_module: dict, selections) -> Optional[int]:
    """How many tests importing *selections* creates, or None if one is not in the cache.

    The worker can import a module the cache leaves out, so an unlisted
    selection would create tests nobody reserved.
    """
    counts = {
        (probe.module_name, probe.class_name): probe.prompt_count
        for probes in probes_by_module.values()
        for probe in probes
    }
    keys = [(s.module_name, s.class_name) for s in selections]
    if any(key not in counts for key in keys):
        return None
    return sum(counts[key] for key in keys)


def _build_sync_preview(
    db: Session,
    probes_by_module: dict,
    test_set_id: str,
    organization_id: str,
):
    """Run the sync service's preview against the database, off the event loop."""
    sync_service = GarakSyncService(db)
    sync_service.preload_probes(probes_by_module)
    return sync_service.get_sync_preview(test_set_id, organization_id)


@router.get("/sync/{test_set_id}/preview", response_model=GarakSyncPreviewResponse)
async def preview_sync(
    test_set_id: str,
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
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
        _, probes_by_module = await _enumerate_probes(probe_service)

        preview = await anyio.to_thread.run_sync(
            _build_sync_preview,
            db,
            probes_by_module,
            test_set_id,
            organization_id,
        )

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
        ) from e


@router.post(
    "/sync/{test_set_id}",
    response_model=GarakSyncTaskResponse,
    status_code=202,
    dependencies=[per_user_rate_limit(GENERATION_RATE_LIMIT)],
)
async def sync_test_set(
    test_set_id: str,
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
    _quota_gate: Organization = Depends(require_quota(QuotaResource.TEST_GENERATION)),
    _job_capacity: None = Depends(require_job_capacity),
):
    """
    Sync a Garak-imported test set with the latest probes.

    Updates the test set to include new probes and remove deprecated ones.
    Some Garak probes produce thousands of prompts, so this runs as a
    background task rather than blocking the request — returns HTTP 202
    Accepted with a `task_id` that can be polled via `GET /jobs/by-celery-id/{task_id}`.
    """
    organization_id, _ = tenant_context
    _, probes_by_module = await _enumerate_probes(probe_service)
    try:
        task_result = await anyio.to_thread.run_sync(
            _launch_sync,
            db,
            probes_by_module,
            test_set_id,
            organization_id,
            current_user,
            _quota_gate,
        )
    except ValueError as e:
        logger.warning(f"Sync validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    return GarakSyncTaskResponse(
        task_id=str(task_result.id),
        test_set_id=test_set_id,
        message=f"Sync started for test set {test_set_id}.",
    )


def _launch_sync(
    db: Session,
    probes_by_module: dict,
    test_set_id: str,
    organization_id: str,
    current_user: User,
    org: Organization,
):
    """Validate the sync target, reserve the tests it would add, and launch the sync job."""
    # Validate the test set is syncable up front so an invalid request gets a
    # synchronous 400 (ValueError) instead of a background task that fails
    # silently. The task re-resolves and extracts the probes itself; we
    # deliberately don't ship probe data (prompts) through the Celery broker
    # (see import_probes for why).
    GarakSyncService(db).resolve_sync_target(test_set_id, organization_id)
    preview = _build_sync_preview(db, probes_by_module, test_set_id, organization_id) or {}
    if preview.get("can_sync") is False:
        raise ValueError(preview.get("error") or "This test set cannot be synced")

    return launch_reserved_job(
        sync_garak_test_set_task,
        org=org,
        resource=QuotaResource.TEST_GENERATION,
        amount=preview.get("to_add", 0),
        current_user=current_user,
        db=db,
        test_set_id=test_set_id,
        entity_type="TestSet",
        entity_id=test_set_id,
    )


@router.post(
    "/generate",
    response_model=GarakGenerateResponse,
    status_code=202,
    dependencies=[per_user_rate_limit(GENERATION_RATE_LIMIT)],
)
def generate_dynamic_probe(
    request: GarakGenerateRequest,
    current_user: User = Depends(require_current_user_or_token),
    probe_service: GarakProbeService = Depends(get_probe_service),
    db: Session = Depends(get_tenant_db_session),
    _quota_gate: Organization = Depends(require_quota(QuotaResource.TEST_GENERATION)),
    _job_capacity: None = Depends(require_job_capacity),
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
    `GET /jobs/by-celery-id/{task_id}`.
    """
    module_name = request.module_name
    class_name = request.class_name

    _require_garak(probe_service)

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

    num_tests = request.num_tests
    if num_tests is None:
        # A random count in [100, 200], capped at what the quota has left.
        num_tests = random.randint(100, 200)
        remaining = check_quota(
            db, str(_quota_gate.id), _quota_gate, QuotaResource.TEST_GENERATION
        ).remaining
        if remaining is not None:
            num_tests = max(min(num_tests, remaining), 1)

    test_set_name = request.name or f"Garak Dynamic: {probe_info.full_name}"

    task_result = launch_reserved_job(
        generate_and_save_test_set,
        org=_quota_gate,
        resource=QuotaResource.TEST_GENERATION,
        amount=num_tests,
        current_user=current_user,
        db=db,
        config=config.model_dump(),
        num_tests=num_tests,
        name=test_set_name,
        metadata=probe_metadata,
        model_id=request.model_id,
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

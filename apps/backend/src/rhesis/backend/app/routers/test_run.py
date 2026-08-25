from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.crud import test_run as test_run_crud
from rhesis.backend.app.crud.telemetry import query_traces
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import authorize_object, project_id_from_scope
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import EnrichedDataKeys
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.telemetry import TraceListResponse, TraceSource, TraceSummary
from rhesis.backend.app.services.test_run import (
    get_test_results_for_test_run,
    rescore_test_run,
    test_run_results_to_csv,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.odata import apply_select
from rhesis.backend.tasks.enums import RunStatus


router = RhesisRouter(
    prefix="/test_runs",
    tags=["test_runs"],
    responses={404: {"description": "Not found"}},
    resource="test_run",
)


@router.post("/", response_model=schemas.TestRun)
@handle_database_exceptions(
    entity_name="test run", custom_unique_message="Test run with this configuration already exists"
)
def create_test_run(
    test_run: schemas.TestRunCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create a new test run."""
    organization_id, user_id = tenant_context
    # Set the user_id to the current user if not provided
    if not test_run.user_id:
        test_run.user_id = current_user.id

    # Set the organization_id if not provided
    if not test_run.organization_id:
        test_run.organization_id = current_user.organization_id

    return test_run_crud.create_test_run(
        db=db, test_run=test_run, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.TestRunDetail])
@with_count_header(model=models.TestRun)
def read_test_runs(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    select: str | None = Query(
        None,
        alias="$select",
        description="Comma-separated list of fields to return",
    ),
    has_experiment: bool | None = Query(
        None,
        description="Filter by experiment association: true = only runs with an experiment, "
        "false = only runs without, omit = all runs",
    ),
    has_reviews: bool | None = Query(
        None,
        description="Filter by human review activity on child test results: "
        "true = runs with at least one reviewed test, "
        "false = runs with no reviewed tests, omit = all runs",
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test runs with their related objects"""
    results = test_run_crud.get_test_runs(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        has_experiment=has_experiment,
        has_reviews=has_reviews,
        organization_id=str(current_user.organization_id),
        user_id=str(current_user.id),
    )
    if select:
        serialized = jsonable_encoder(results)
        return JSONResponse(content=apply_select(serialized, select))

    # Attach accurate per-run pass/fail counts so list views (e.g. the test
    # runs grid pass-rate column) don't rely on the stale
    # ``attributes.completed_tests`` / ``failed_tests`` counters. Aggregated in
    # a single query to avoid the N+1 cost of one stats query per run.
    from rhesis.backend.tasks.execution.result_processor import (
        get_review_statistics_for_runs,
        get_test_statistics_for_runs,
        inject_review_counts_into_serialized_runs,
    )

    run_ids = [run.id for run in results]
    organization_id = str(current_user.organization_id)
    run_stats = get_test_statistics_for_runs(db, run_ids, organization_id=organization_id)
    review_stats = get_review_statistics_for_runs(db, run_ids, organization_id=organization_id)
    serialized = []
    for run in results:
        item = schemas.TestRunDetail.model_validate(run).model_dump(mode="json")
        item["stats"] = run_stats.get(
            str(item.get("id")),
            {"total": 0, "passed": 0, "failed": 0, "errors": 0},
        )
        serialized.append(item)
    inject_review_counts_into_serialized_runs(serialized, review_stats)
    return JSONResponse(content=serialized)


@router.get("/{test_run_id}", response_model=schemas.TestRunDetail)
def read_test_run(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test run by ID with its related objects"""
    organization_id, user_id = tenant_context
    db_test_run = test_run_crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    return db_test_run


@router.get("/{test_run_id}/requirements", response_model=List[schemas.Requirement])
def get_test_run_requirements(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
):
    """Get requirements that have test results for this test run with organization filtering"""
    organization_id, user_id = tenant_context  # SECURITY: Get tenant context
    requirements = test_run_crud.get_test_run_requirements(
        db, test_run_id=test_run_id, organization_id=organization_id
    )
    return requirements


@router.get("/{test_run_id}/metrics", response_model=List[str])
def get_test_run_metrics(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get distinct metric names actually evaluated in this test run's results"""
    organization_id, _user_id = tenant_context
    return test_run_crud.get_test_run_metrics(
        db, test_run_id=test_run_id, organization_id=organization_id
    )


@router.put("/{test_run_id}", response_model=schemas.TestRun)
@handle_database_exceptions(
    entity_name="test run", custom_unique_message="Test run with this configuration already exists"
)
def update_test_run(
    test_run_id: UUID,
    test_run: schemas.TestRunUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update an existing test run."""
    organization_id, user_id = tenant_context
    db_test_run = test_run_crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    return test_run_crud.update_test_run(
        db=db,
        test_run_id=test_run_id,
        test_run=test_run,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.delete("/bulk", response_model=schemas.TestRunBulkDeleteResponse)
def bulk_delete_test_runs(
    request: schemas.TestRunBulkDeleteRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete multiple test runs at once.

    Only the creator of a test run may delete it -- ids that exist but belong
    to someone else land in "forbidden_ids", not silently skipped or deleted,
    same rule as the single-item delete route below. Active runs (Queued or
    Progress) among the ones actually deleted have their Celery task revoked.

    Registered before /{test_run_id} below -- FastAPI matches routes in
    registration order, so a literal /bulk path must come first or a
    /{test_run_id}-shaped route would swallow it (treating "bulk" as an id).
    """
    from rhesis.backend.celery.core import app as celery_app

    organization_id, user_id = tenant_context
    active_statuses = {RunStatus.QUEUED.value, RunStatus.PROGRESS.value}
    task_ids_by_run = test_run_crud.get_test_run_task_ids(
        db, request.test_run_ids, organization_id=organization_id, user_id=user_id
    )

    result = test_run_crud.bulk_delete_test_runs(
        db=db,
        test_run_ids=request.test_run_ids,
        organization_id=organization_id,
        user_id=user_id,
    )

    for deleted_id in result["deleted_ids"]:
        status_name, task_id = task_ids_by_run.get(UUID(deleted_id), (None, None))
        if status_name in active_statuses and task_id:
            celery_app.control.revoke(task_id)

    return result


@router.delete("/{test_run_id}", response_model=schemas.TestRun)
def delete_test_run(
    test_run_id: UUID,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test run.

    Only the creator may delete their own test run (object-level :own gate).
    If the run is still active (Queued or Progress) its Celery task is revoked
    before the record is removed so the worker does not continue executing a
    run that no longer exists in the database.
    """
    from rhesis.backend.celery.core import app as celery_app

    organization_id, user_id = tenant_context
    db_test_run = test_run_crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    if not authorize_object(
        principal, Permission.TestRun.DELETE_OWN, db_test_run, project_id=project_id, db=db
    ):
        raise HTTPException(status_code=403, detail="Not authorized to delete this test run")

    active_statuses = {RunStatus.QUEUED.value, RunStatus.PROGRESS.value}
    current_status = db_test_run.status.name if db_test_run.status else None
    if current_status in active_statuses:
        task_id = (db_test_run.attributes or {}).get("task_id")
        if task_id:
            celery_app.control.revoke(task_id)

    return test_run_crud.delete_test_run(
        db=db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )


@router.post(
    "/{test_run_id}/cancel", response_model=schemas.TestRun, **capability(Permission.TestRun.UPDATE)
)
def cancel_test_run(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Cancel a queued or in-progress test run.

    Adds the underlying Celery task to the broker's revoke set when a task_id
    is present in the run's attributes (no signal is sent; the worker checks the
    revoke set cooperatively via the cancellation watchdog).  The status is
    immediately set to Cancelled so the caller sees the new state without
    waiting for the worker to acknowledge.
    """
    from rhesis.backend.celery.core import app as celery_app
    from rhesis.backend.tasks.execution.run import update_test_run_status

    organization_id, user_id = tenant_context
    db_test_run = test_run_crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    current_status = db_test_run.status.name if db_test_run.status else None
    cancellable_statuses = {RunStatus.QUEUED.value, RunStatus.PROGRESS.value}
    if current_status not in cancellable_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel a test run with status '{current_status}'",
        )

    task_id = (db_test_run.attributes or {}).get("task_id")
    if task_id:
        # Broadcast revoke to all workers so the task is skipped if still
        # queued. We do NOT pass terminate=True because the worker uses a
        # thread pool — SIGTERM targets the whole process, not the thread.
        # Cancellation of an already-running batch relies on the early-exit
        # check at the top of execute_test_configuration.
        celery_app.control.revoke(task_id)

    update_test_run_status(db, db_test_run, RunStatus.CANCELLED.value)

    return test_run_crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )


@router.post("/{test_run_id}/rescore", **capability(Permission.TestRun.UPDATE))
def rescore_test_run_endpoint(
    test_run_id: UUID,
    request: schemas.TestRunRescoreRequest = None,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Re-score all tests in a test run with new metrics.

    No endpoints will be invoked -- only metric evaluation on stored
    outputs from the original test run.

    Args:
        test_run_id: UUID of the test run to re-score
        request: Optional rescore request with metric overrides
    """
    organization_id, user_id = tenant_context

    # Convert metrics from schema to dicts if provided
    metrics = None
    if request and request.metrics:
        metrics = [
            {
                "id": str(m.id),
                "name": m.name,
                "scope": m.scope,
            }
            for m in request.metrics
        ]

    evaluation_model_id = None
    if request and request.evaluation_model_id:
        evaluation_model_id = request.evaluation_model_id

    try:
        result = rescore_test_run(
            db=db,
            reference_test_run_id=str(test_run_id),
            current_user=current_user,
            metrics=metrics,
            evaluation_model_id=evaluation_model_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{test_run_id}/download", response_class=StreamingResponse)
def download_test_run_results(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Download test run results as CSV"""
    try:
        organization_id, user_id = tenant_context
        # Check if test run exists and user has access
        db_test_run = test_run_crud.get_test_run(
            db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
        )
        if db_test_run is None:
            raise HTTPException(status_code=404, detail="Test run not found")

        # Get test results data
        test_results_data = get_test_results_for_test_run(
            db, test_run_id, organization_id=str(current_user.organization_id)
        )

        # Convert to CSV
        csv_data = test_run_results_to_csv(test_results_data)

        # Create response
        response = StreamingResponse(iter([csv_data]), media_type="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=test_run_{test_run_id}_results.csv"
        )
        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{test_run_id}/traces", response_model=TraceListResponse)
def get_test_run_traces(
    test_run_id: UUID,
    limit: int = Query(100, ge=1, le=1000, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> TraceListResponse:
    """
    Get all traces associated with a test run.

    Returns traces from all test executions within this test run,
    useful for debugging and analyzing test execution requirement.

    **Authentication**: Requires valid user session or API key

    **Pagination**:
    - `limit`: Number of results per page (default: 100, max: 1000)
    - `offset`: Number of results to skip (default: 0)

    Returns:
        Paginated list of trace summaries for this test run
    """
    organization_id, user_id = tenant_context

    # Verify test run exists and user has access
    db_test_run = test_run_crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Get project_id from test run with proper null checks
    if not db_test_run.test_configuration:
        raise HTTPException(
            status_code=500,
            detail=f"Test run {test_run_id} has no associated test configuration",
        )
    if not db_test_run.test_configuration.endpoint:
        raise HTTPException(
            status_code=500,
            detail=f"Test configuration for test run {test_run_id} has no associated endpoint",
        )
    if not db_test_run.test_configuration.endpoint.project_id:
        raise HTTPException(
            status_code=500,
            detail=f"Endpoint for test run {test_run_id} has no associated project",
        )

    project_id = str(db_test_run.test_configuration.endpoint.project_id)

    # Single DB query returns TraceRow(trace, span_count, total) per row
    rows = query_traces(
        db=db,
        organization_id=organization_id,
        project_id=project_id,
        root_spans_only=True,
        trace_source=TraceSource.TEST,
        test_run_id=str(test_run_id),
        limit=limit,
        offset=offset,
    )

    total = rows[0].total if rows else 0

    summaries = []
    for row in rows:
        trace = row.trace
        has_errors = trace.status_code == "ERROR"
        total_tokens = trace.total_tokens or 0
        total_cost_usd = 0.0
        total_cost_eur = 0.0
        costs = (trace.enriched_data or {}).get(EnrichedDataKeys.COSTS, {})
        if costs:
            total_cost_usd = costs.get(EnrichedDataKeys.TOTAL_COST_USD, 0.0)
            total_cost_eur = costs.get(EnrichedDataKeys.TOTAL_COST_EUR, 0.0)

        conversation_input = None
        if isinstance(trace.attributes, dict):
            raw_input = trace.attributes.get("rhesis.conversation.input")
            if raw_input is not None:
                conversation_input = str(raw_input)

        summary = TraceSummary(
            trace_id=trace.trace_id,
            project_id=str(trace.project_id),
            environment=trace.environment,
            conversation_input=conversation_input,
            start_time=trace.start_time,
            duration_ms=trace.duration_ms or 0.0,
            span_count=row.span_count,
            root_operation=trace.span_name,
            status_code=trace.status_code,
            has_errors=has_errors,
            total_tokens=total_tokens if total_tokens > 0 else None,
            total_cost_usd=total_cost_usd if total_cost_usd > 0 else None,
            total_cost_eur=total_cost_eur if total_cost_eur > 0 else None,
            test_run_id=str(trace.test_run_id) if trace.test_run_id else None,
            test_result_id=str(trace.test_result_id) if trace.test_result_id else None,
            test_id=str(trace.test_id) if trace.test_id else None,
        )
        summaries.append(summary)

    return TraceListResponse(
        traces=summaries,
        total=total,
        limit=limit,
        offset=offset,
    )

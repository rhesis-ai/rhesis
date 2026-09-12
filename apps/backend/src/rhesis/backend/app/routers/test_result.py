from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import authorize_object, project_id_from_scope
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.crud import file as file_crud
from rhesis.backend.app.crud import test_result as test_result_crud
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.odata import apply_select

router = RhesisRouter(
    prefix="/test_results",
    tags=["test_results"],
    responses={404: {"description": "Not found"}},
    resource="test_result",
)


@router.post("/", response_model=schemas.TestResult)
@handle_database_exceptions(
    entity_name="test result", custom_unique_message="test result with this name already exists"
)
def create_test_result(
    test_result: schemas.TestResultCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create a new test result.

    The test result can include:
    - test_metrics: Automated metric evaluations
    - test_output: The actual test execution output

    Note: If test_metrics are provided but status_id is not, the status will be
    automatically set based on whether all metrics passed.
    """
    organization_id, user_id = tenant_context

    # Set the user_id to the current user if not provided
    if not test_result.user_id:
        test_result.user_id = current_user.id

    # Auto-set status based on test_metrics if not provided
    metrics = test_result.test_metrics.get("metrics", {}) if test_result.test_metrics else {}
    if not test_result.status_id and metrics:
        from rhesis.backend.app.outcomes import (
            classify_metrics,
            outcome_of,
            outcome_to_test_result_status_name,
        )
        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        execution, verdict = classify_metrics(metrics)
        status_value = outcome_to_test_result_status_name(outcome_of(execution, verdict))
        status = get_or_create_status(
            db, status_value, "TestResult", organization_id=organization_id
        )
        test_result.status_id = status.id
        test_result.execution = execution.value
        test_result.verdict = verdict.value if verdict else None
    elif test_result.status_id:
        # The caller supplied a status directly, with no metrics for
        # classify_metrics to work from -- derive execution/verdict from
        # the status's own name so the source-of-truth columns still get
        # populated for this path too, not only the auto-status one above.
        from rhesis.backend.app.outcomes import execution_verdict_from_status_name

        status_row = (
            db.query(models.Status).filter(models.Status.id == test_result.status_id).first()
        )
        execution, verdict = execution_verdict_from_status_name(
            status_row.name if status_row else None
        )
        test_result.execution = execution.value
        test_result.verdict = verdict.value if verdict else None

    return test_result_crud.create_test_result(
        db=db, test_result=test_result, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.TestResultDetail])
@with_count_header(model=models.TestResult)
def read_test_results(
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
    strip_conversation: bool = Query(
        False,
        description=(
            "Drop test_output.conversation_summary from each result -- the full multi-turn "
            "transcript, useful for a caller rendering a conversation view but unneeded on a "
            "results grid."
        ),
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test results"""
    organization_id, user_id = tenant_context
    results = test_result_crud.get_test_results(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
        strip_conversation=strip_conversation,
    )
    if select:
        serialized = jsonable_encoder(results)
        return JSONResponse(content=apply_select(serialized, select))
    return results


@router.get("/{test_result_id}", response_model=schemas.TestResultDetail)
def read_test_result(
    test_result_id: UUID,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test result by ID"""
    organization_id, user_id = tenant_context
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    return db_test_result


@router.put("/{test_result_id}", response_model=schemas.TestResult)
def update_test_result(
    test_result_id: UUID,
    test_result: schemas.TestResultUpdate,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update a test result.

    Supports updating:
    - test_metrics: Automated evaluations
    - status_id: Overall status of the test result

    Note: If test_metrics are updated but status_id is not provided, the status will be
    automatically updated based on whether all metrics passed.
    """
    organization_id, user_id = tenant_context
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    if not authorize_object(
        principal, Permission.TestResult.UPDATE_OWN, db_test_result, project_id=project_id, db=db
    ):
        raise HTTPException(status_code=403, detail="Not authorized to update this test result")

    # Auto-update status based on test_metrics if status_id is not explicitly provided
    metrics = test_result.test_metrics.get("metrics", {}) if test_result.test_metrics else {}
    if metrics and not test_result.status_id:
        from rhesis.backend.app.outcomes import (
            classify_metrics,
            outcome_of,
            outcome_to_test_result_status_name,
        )
        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        execution, verdict = classify_metrics(metrics)
        status_value = outcome_to_test_result_status_name(outcome_of(execution, verdict))
        status = get_or_create_status(
            db, status_value, "TestResult", organization_id=organization_id
        )
        test_result.status_id = status.id
        test_result.execution = execution.value
        test_result.verdict = verdict.value if verdict else None
    elif test_result.status_id:
        # The caller is changing status directly, with no metrics for
        # classify_metrics to work from -- derive execution/verdict from
        # the new status's own name so they stay in sync with it.
        from rhesis.backend.app.outcomes import execution_verdict_from_status_name

        status_row = (
            db.query(models.Status).filter(models.Status.id == test_result.status_id).first()
        )
        execution, verdict = execution_verdict_from_status_name(
            status_row.name if status_row else None
        )
        test_result.execution = execution.value
        test_result.verdict = verdict.value if verdict else None

    return test_result_crud.update_test_result(
        db=db,
        test_result_id=test_result_id,
        test_result=test_result,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.delete("/{test_result_id}", response_model=schemas.TestResult)
def delete_test_result(
    test_result_id: UUID,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test result. Only the creator may delete their own result."""
    organization_id, user_id = tenant_context
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    if not authorize_object(
        principal, Permission.TestResult.DELETE_OWN, db_test_result, project_id=project_id, db=db
    ):
        raise HTTPException(status_code=403, detail="Not authorized to delete this test result")

    return test_result_crud.delete_test_result(
        db=db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )


@router.get("/{test_result_id}/files", response_model=List[schemas.FileResponse])
def list_test_result_files(
    test_result_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """List output files attached to a test result."""
    organization_id, user_id = tenant_context
    return file_crud.get_files_for_entity(
        db, test_result_id, "TestResult", organization_id, user_id
    )

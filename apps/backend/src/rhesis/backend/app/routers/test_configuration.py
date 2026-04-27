import uuid as uuid_lib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.execution_validation import (
    handle_execution_error,
    validate_execution_model,
)
from rhesis.backend.app.utils.odata import apply_select
from rhesis.backend.app.utils.schema_factory import create_detailed_schema
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.tasks.execution.run import create_test_run, update_test_run_status
from rhesis.backend.tasks.test_configuration import execute_test_configuration

# Create the detailed schema for TestConfiguration
TestConfigurationDetailSchema = create_detailed_schema(
    schemas.TestConfiguration, models.TestConfiguration
)

router = APIRouter(
    prefix="/test_configurations",
    tags=["test_configurations"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.TestConfiguration)
@handle_database_exceptions(
    entity_name="test configuration",
    custom_unique_message="test configuration with this name already exists",
)
def create_test_configuration(
    test_configuration: schemas.TestConfigurationCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create a new test configuration."""
    organization_id, user_id = tenant_context

    # Set the user_id to the current user if not provided
    if not test_configuration.user_id:
        test_configuration.user_id = current_user.id

    # Set the organization_id if not provided
    if not test_configuration.organization_id:
        test_configuration.organization_id = current_user.organization_id

    return crud.create_test_configuration(
        db=db,
        test_configuration=test_configuration,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/", response_model=list[TestConfigurationDetailSchema])
@with_count_header(model=models.TestConfiguration)
def read_test_configurations(
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
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test configurations with their related objects"""
    organization_id, user_id = tenant_context
    results = crud.get_test_configurations(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    if select:
        serialized = jsonable_encoder(results)
        return JSONResponse(content=apply_select(serialized, select))
    return results


@router.get("/{test_configuration_id}", response_model=TestConfigurationDetailSchema)
def read_test_configuration(
    test_configuration_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test configuration by ID with its related objects"""
    organization_id, user_id = tenant_context
    db_test_configuration = crud.get_test_configuration(
        db,
        test_configuration_id=test_configuration_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_test_configuration is None:
        raise HTTPException(status_code=404, detail="Test configuration not found")
    return db_test_configuration


@router.put("/{test_configuration_id}", response_model=schemas.TestConfiguration)
def update_test_configuration(
    test_configuration_id: UUID,
    test_configuration: schemas.TestConfigurationUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update an existing test configuration."""
    organization_id, user_id = tenant_context
    db_test_configuration = crud.get_test_configuration(
        db,
        test_configuration_id=test_configuration_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_test_configuration is None:
        raise HTTPException(status_code=404, detail="Test configuration not found")

    return crud.update_test_configuration(
        db=db,
        test_configuration_id=test_configuration_id,
        test_configuration=test_configuration,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.delete("/{test_configuration_id}", response_model=schemas.TestConfiguration)
def delete_test_configuration(
    test_configuration_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test configuration"""
    organization_id, user_id = tenant_context
    db_test_configuration = crud.get_test_configuration(
        db,
        test_configuration_id=test_configuration_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_test_configuration is None:
        raise HTTPException(status_code=404, detail="Test configuration not found")

    return crud.delete_test_configuration(
        db=db,
        test_configuration_id=test_configuration_id,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.post("/{test_configuration_id}/execute")
def execute_test_configuration_endpoint(
    test_configuration_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_execution_model),
):
    """
    Execute a test configuration by running its test set.
    """
    try:
        organization_id, user_id = tenant_context
        # Verify the test configuration exists
        db_test_configuration = crud.get_test_configuration(
            db,
            test_configuration_id=test_configuration_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if db_test_configuration is None:
            raise HTTPException(status_code=404, detail="Test configuration not found")

        # Pre-generate the Celery task ID so it can be stored in the test
        # run record before the task is dispatched.  This guarantees the
        # cancel endpoint always has a task_id to revoke, even if the
        # request is cancelled before the worker starts executing.
        celery_task_id = str(uuid_lib.uuid4())

        # Create the test run immediately with Queued status so the user
        # can see it in the UI even before a worker picks up the task.
        # Pass task_id so it is persisted atomically with the record.
        test_run = create_test_run(
            db,
            db_test_configuration,
            task_info={"id": celery_task_id},
            current_user_id=str(current_user.id) if current_user else None,
        )
        db.commit()

        # Dispatch the task using the same pre-generated ID so Celery
        # registers it under the known UUID.
        try:
            task = task_launcher(
                execute_test_configuration,
                str(test_configuration_id),
                test_run_id=str(test_run.id),
                current_user=current_user,
                task_id=celery_task_id,
            )
        except Exception as exc:
            # Mark the queued test run as failed so it doesn't stay stuck
            update_test_run_status(db, test_run, RunStatus.FAILED.value, error=str(exc))
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to submit task: {exc}",
            ) from exc

        return {
            "test_configuration_id": str(test_configuration_id),
            "test_run_id": str(test_run.id),
            "task_id": task.id,
            "status": "submitted",
            "endpoint_id": str(db_test_configuration.endpoint_id),
            "test_set_id": str(db_test_configuration.test_set_id)
            if db_test_configuration.test_set_id
            else None,
            "user_id": str(db_test_configuration.user_id),
        }
    except HTTPException:
        raise
    except Exception as e:
        http_exception = handle_execution_error(e, operation="execute test configuration")
        raise http_exception

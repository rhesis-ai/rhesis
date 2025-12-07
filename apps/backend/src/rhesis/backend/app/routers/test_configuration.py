from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
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
from rhesis.backend.app.utils.schema_factory import create_detailed_schema
from rhesis.backend.tasks import task_launcher
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
    """
    Create test configuration with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
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


@router.get("/", response_model=List[TestConfigurationDetailSchema])
@with_count_header(model=models.TestConfiguration)
def read_test_configurations(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test configurations with their related objects"""
    organization_id, user_id = tenant_context
    test_configurations = crud.get_test_configurations(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    return test_configurations


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
    """
    Update test_configuration with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
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
):
    """
    Execute a test configuration by running its test set.
    """
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

    # Check if the user has permission to execute this test configuration
    if db_test_configuration.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to execute this test configuration"
        )

    # Submit the celery task with the task_launcher which automatically adds context
    task = task_launcher(
        execute_test_configuration, str(test_configuration_id), current_user=current_user
    )

    return {
        "test_configuration_id": str(test_configuration_id),
        "task_id": task.id,
        "status": "submitted",
        "endpoint_id": str(db_test_configuration.endpoint_id),
        "test_set_id": str(db_test_configuration.test_set_id)
        if db_test_configuration.test_set_id
        else None,
        "user_id": str(db_test_configuration.user_id),
    }

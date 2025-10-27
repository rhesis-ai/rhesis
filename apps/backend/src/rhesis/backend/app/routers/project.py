import uuid

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

# Create the detailed schema for TestRun
ProjectDetailSchema = create_detailed_schema(schemas.Project, models.Project)

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Project)
@handle_database_exceptions(
    entity_name="project", custom_unique_message="Project with this name already exists"
)
async def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create project with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context

    # Set the current user as the creator if not specified
    if not project.user_id:
        project.user_id = current_user.id

    # Set the current user as the owner if not specified
    if not project.owner_id:
        project.owner_id = current_user.id

    return crud.create_project(
        db=db, project=project, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[ProjectDetailSchema])
@with_count_header(model=models.Project)
async def read_projects(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all projects with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_projects(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{project_id}")
def read_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get project with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_project = crud.get_project(
        db, project_id=project_id, organization_id=organization_id, user_id=user_id
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return db_project


@router.put("/{project_id}", response_model=schemas.Project)
def update_project(
    project_id: uuid.UUID,
    project: schemas.ProjectUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update project with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_project = crud.get_project(
        db, project_id=project_id, organization_id=organization_id, user_id=user_id
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has permission to update this project
    if db_project.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this project")

    return crud.update_project(
        db, project_id=project_id, project=project, organization_id=organization_id, user_id=user_id
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete project with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_project = crud.get_project(
        db, project_id=project_id, organization_id=organization_id, user_id=user_id
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has permission to delete this project
    if db_project.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")

    return crud.delete_project(
        db, project_id=project_id, organization_id=organization_id, user_id=user_id
    )

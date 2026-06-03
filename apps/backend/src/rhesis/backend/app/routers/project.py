import uuid

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
from rhesis.backend.app.utils.odata import apply_select
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

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
    """Create a new project. The creating user is automatically enrolled as a member."""
    from rhesis.backend.app.services.organization import enroll_user_in_project

    organization_id, user_id = tenant_context

    if not project.user_id:
        project.user_id = current_user.id

    if not project.owner_id:
        project.owner_id = current_user.id

    new_project = crud.create_project(
        db=db, project=project, organization_id=organization_id, user_id=user_id
    )

    # Auto-enroll the creator so the project is immediately visible in their listing.
    enroll_user_in_project(
        db=db,
        user_id=str(current_user.id),
        project_id=str(new_project.id),
        organization_id=organization_id,
    )
    db.commit()
    db.refresh(new_project)

    return new_project


@router.get("/mine", response_model=list[ProjectDetailSchema])
def read_my_projects(
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Return all projects the current user is a member of."""
    organization_id, _user_id = tenant_context
    return crud.get_my_projects(
        db=db,
        user_id=current_user.id,
        organization_id=organization_id,
    )


@router.get("/", response_model=list[ProjectDetailSchema])
async def read_projects(
    response: Response,
    skip: int = 0,
    limit: int = 10,
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
    """Get all projects the current user is a member of."""
    organization_id, user_id = tenant_context
    results = crud.get_projects(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    # Count uses the same membership filter so X-Total-Count matches pagination.
    total = crud.count_projects(
        db=db, filter=filter, organization_id=organization_id, user_id=user_id
    )
    response.headers["X-Total-Count"] = str(total)
    if select:
        serialized = jsonable_encoder(results)
        result = JSONResponse(content=apply_select(serialized, select))
        result.headers["X-Total-Count"] = str(total)
        return result
    return results


@router.get("/{project_id}/members", response_model=list[schemas.ProjectMember])
def read_project_members(
    project_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """List all members of a project."""
    organization_id, _user_id = tenant_context
    db_project = crud.get_project(
        db, project_id=project_id, organization_id=organization_id
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return crud.get_project_members(db=db, project_id=project_id, organization_id=organization_id)


@router.post("/{project_id}/members", response_model=schemas.ProjectMember, status_code=201)
def add_project_member(
    project_id: uuid.UUID,
    body: schemas.ProjectMemberCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Add a user as a member of a project."""
    organization_id, _user_id = tenant_context
    db_project = crud.get_project(
        db, project_id=project_id, organization_id=organization_id
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate that the target user is in the same org
    from rhesis.backend.app.models.user import User as UserModel

    target_user = (
        db.query(UserModel)
        .filter(
            UserModel.id == body.user_id,
            UserModel.organization_id == db_project.organization_id,
        )
        .first()
    )
    if target_user is None:
        raise HTTPException(
            status_code=404, detail="User not found in this organization"
        )

    return crud.add_project_member(
        db=db,
        project_id=project_id,
        user_id=body.user_id,
        organization_id=organization_id,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Remove a user from a project.

    The project owner cannot be removed, and a user cannot remove themselves.
    Both rules are enforced by the service layer regardless of how it is called.
    """
    from rhesis.backend.app.services.organization import (
        ProjectOwnerRemovalError,
        ProjectSelfRemovalError,
    )

    organization_id, _tenant_user_id = tenant_context
    db_project = crud.get_project(
        db, project_id=project_id, organization_id=organization_id
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        removed = crud.remove_project_member(
            db=db,
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            requester_user_id=current_user.id,
        )
    except ProjectSelfRemovalError:
        raise HTTPException(
            status_code=400, detail="You cannot remove yourself from a project"
        )
    except ProjectOwnerRemovalError:
        raise HTTPException(status_code=400, detail="Cannot remove the project owner")

    if not removed:
        raise HTTPException(status_code=404, detail="Membership not found")


@router.get("/{project_id}", response_model=ProjectDetailSchema)
def read_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a project by ID."""
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
    """Update a project by ID."""
    organization_id, user_id = tenant_context
    db_project = crud.get_project(
        db, project_id=project_id, organization_id=organization_id, user_id=user_id
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return crud.update_project(
        db, project_id=project_id, project=project, organization_id=organization_id, user_id=user_id
    )


@router.delete("/{project_id}", response_model=schemas.Project)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a project by ID."""
    organization_id, user_id = tenant_context
    db_project = crud.get_project(
        db, project_id=project_id, organization_id=organization_id, user_id=user_id
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return crud.delete_project(
        db, project_id=project_id, organization_id=organization_id, user_id=user_id
    )

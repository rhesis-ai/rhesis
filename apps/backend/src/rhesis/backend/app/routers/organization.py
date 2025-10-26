import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import (
    require_current_user_or_token,
    require_current_user_or_token_without_context,
)
from rhesis.backend.app.dependencies import (
    get_db_session,
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.organization import load_initial_data, rollback_initial_data
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/organizations", tags=["organizations"], responses={404: {"description": "Not found"}}
)


@router.post("/", response_model=schemas.Organization)
@handle_database_exceptions(
    entity_name="organization", custom_unique_message="Organization with this name already exists"
)
async def create_organization(
    organization: schemas.OrganizationCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    if not organization.owner_id or not organization.user_id:
        raise HTTPException(status_code=400, detail="owner_id and user_id are required")

    return crud.create_organization(db=db, organization=organization)


@router.get("/", response_model=list[schemas.Organization])
@with_count_header(model=models.Organization)
async def read_organizations(
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
    """Get all organizations with their related objects"""
    try:
        organization_id, user_id = tenant_context
        return crud.get_organizations(
            db=db,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
            organization_id=organization_id,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve organizations: {str(e)}")


@router.get("/{organization_id}", response_model=schemas.Organization)
def read_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        tenant_organization_id, user_id = tenant_context
        db_organization = crud.get_organization(
            db,
            organization_id=organization_id,
            tenant_organization_id=tenant_organization_id,
            user_id=user_id,
        )
        if db_organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        return db_organization
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve organization: {str(e)}")


@router.delete("/{organization_id}", response_model=schemas.Organization)
def delete_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized to delete organizations")
        db_organization = crud.delete_organization(db, organization_id=organization_id)
        if db_organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        return db_organization
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete organization: {str(e)}")


@router.put("/{organization_id}", response_model=schemas.Organization)
@handle_database_exceptions(
    entity_name="organization", custom_unique_message="Organization with this name already exists"
)
def update_organization(
    organization_id: uuid.UUID,
    organization: schemas.OrganizationUpdate,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    db_organization = crud.update_organization(
        db, organization_id=organization_id, organization=organization
    )
    if db_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return db_organization


@router.post("/{organization_id}/load-initial-data", response_model=dict)
async def initialize_organization_data(
    organization_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Load initial data for an organization if onboarding is not complete."""
    try:
        org = crud.get_organization(db, organization_id=organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        if org.is_onboarding_complete:
            raise HTTPException(status_code=400, detail="Organization already initialized")

        # Load initial data and get the default model ID
        default_model_id = load_initial_data(db, str(organization_id), str(current_user.id))

        # Update user settings with the default model for both generation and evaluation
        if default_model_id:
            # Get the user to update settings
            user = db.query(models.User).filter(models.User.id == current_user.id).first()
            if user:
                # Use the UserSettingsManager to properly update settings
                user.settings.update(
                    {
                        "models": {
                            "generation": {"model_id": default_model_id},
                            "evaluation": {"model_id": default_model_id},
                        }
                    }
                )
                # Persist the updated settings back to the database
                user.user_settings = user.settings.raw
                db.flush()

        # Mark onboarding as completed
        org.is_onboarding_complete = True
        # Transaction commit is handled by the session context manager

        return {
            "status": "success",
            "message": "Initial data loaded successfully",
            "default_model_id": default_model_id,
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize organization data: {str(e)}"
        )


@router.post("/{organization_id}/rollback-initial-data", response_model=dict)
async def rollback_organization_data(
    organization_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Rollback initial data for an organization."""
    try:
        print(f"Rolling back initial data for organization {organization_id}")
        org = crud.get_organization(db, organization_id=organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        if not org.is_onboarding_complete:
            raise HTTPException(status_code=400, detail="Organization not initialized yet")

        rollback_initial_data(db, str(organization_id))

        # Mark onboarding as incomplete
        org.is_onboarding_complete = False
        # Transaction commit is handled by the session context manager

        return {"status": "success", "message": "Initial data rolled back successfully"}
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to rollback organization data: {str(e)}"
        )

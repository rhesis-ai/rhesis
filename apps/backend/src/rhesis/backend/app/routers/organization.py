import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import (
    require_current_user_or_token,
    require_current_user_or_token_without_context,
)
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.organization import load_initial_data, rollback_initial_data
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.Organization)
async def create_organization(
    organization: schemas.OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    if not organization.owner_id or not organization.user_id:
        raise HTTPException(status_code=400, detail="owner_id and user_id are required")

    try:
        return crud.create_organization(db=db, organization=organization)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create organization: {str(e)}")


@router.get("/", response_model=list[schemas.Organization])
@with_count_header(model=models.Organization)
async def read_organizations(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all organizations with their related objects"""
    try:
        return crud.get_organizations(
            db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve organizations: {str(e)}")


@router.get("/{organization_id}", response_model=schemas.Organization)
def read_organization(
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        db_organization = crud.get_organization(db, organization_id=organization_id)
        if db_organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        return db_organization
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve organization: {str(e)}")


@router.delete("/{organization_id}", response_model=schemas.Organization)
def delete_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
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
def update_organization(
    organization_id: uuid.UUID,
    organization: schemas.OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        db_organization = crud.update_organization(
            db, organization_id=organization_id, organization=organization
        )
        if db_organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        return db_organization
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update organization: {str(e)}")


@router.post("/{organization_id}/load-initial-data", response_model=dict)
async def initialize_organization_data(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Load initial data for an organization if onboarding is not complete."""
    try:
        org = crud.get_organization(db, organization_id=organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        if org.is_onboarding_complete:
            raise HTTPException(status_code=400, detail="Organization already initialized")

        load_initial_data(db, str(organization_id), str(current_user.id))

        # Mark onboarding as completed
        org.is_onboarding_complete = True
        db.commit()

        return {"status": "success", "message": "Initial data loaded successfully"}
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
    db: Session = Depends(get_db),
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
        db.commit()

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

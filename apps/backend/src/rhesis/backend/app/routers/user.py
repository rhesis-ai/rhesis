import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

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
from rhesis.backend.app.routers.auth import create_session_token
from rhesis.backend.app.schemas.user import UserSettings, UserSettingsUpdate
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.rate_limit import INVITATION_RATE_LIMIT, user_limiter
from rhesis.backend.app.utils.validation import validate_and_normalize_email
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.notifications import email_service

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token_without_context)],
)


@router.post("/", response_model=schemas.User)
@user_limiter.limit(INVITATION_RATE_LIMIT)
@handle_database_exceptions(
    entity_name="user", custom_unique_message="User with this email already exists"
)
async def create_user(
    request: Request,
    user: schemas.UserCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    # Set the organization_id from the current user
    user.organization_id = current_user.organization_id

    # Validate and normalize email
    try:
        normalized_email = validate_and_normalize_email(user.email)
        user.email = normalized_email
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check for existing user with the same email
    existing_user = crud.get_user_by_email(db, user.email)
    if existing_user:
        # User already exists - check if they can be re-invited
        if existing_user.organization_id is not None:
            # User belongs to another organization
            raise HTTPException(
                status_code=409,
                detail="This user already belongs to an organization. "
                "They must leave their current organization before joining yours.",
            )

        # User exists but has no organization (previously left/removed)
        # Re-invite them by updating their organization_id
        existing_user.organization_id = current_user.organization_id

        # Update other fields from the invitation if provided
        if user.name:
            existing_user.name = user.name
        if user.given_name:
            existing_user.given_name = user.given_name
        if user.family_name:
            existing_user.family_name = user.family_name

        db.flush()
        created_user = existing_user
        send_invite = user.send_invite
    else:
        # New user - create them
        # Extract send_invite flag before creating user (since it's not part of the model)
        send_invite = user.send_invite

        # Create the user (crud function will automatically exclude send_invite)
        created_user = crud.create_user(db=db, user=user)

    # Send invitation email if requested
    if send_invite and email_service.is_configured:
        try:
            logger.info(f"Sending invitation email to {created_user.email}")

            # Get organization information for the email
            organization = None
            if current_user.organization_id:
                organization = (
                    db.query(models.Organization)
                    .filter(models.Organization.id == current_user.organization_id)
                    .first()
                )

            organization_name = organization.name if organization else "Your Organization"
            organization_website = organization.website if organization else None
            inviter_name = (
                current_user.name
                or f"{current_user.given_name or ''} {current_user.family_name or ''}".strip()
                or "Team Member"
            )

            # Send the invitation email
            success = email_service.send_team_invitation_email(
                recipient_email=created_user.email,
                recipient_name=created_user.name or created_user.given_name,
                organization_name=organization_name,
                organization_website=organization_website,
                inviter_name=inviter_name,
                inviter_email=current_user.email,
            )

            if success:
                logger.info(f"Successfully sent invitation email to {created_user.email}")
            else:
                logger.warning(f"Failed to send invitation email to {created_user.email}")

        except Exception as e:
            logger.error(f"Error sending invitation email to {created_user.email}: {str(e)}")
            # Don't fail user creation if email sending fails

    return created_user


@router.get("/", response_model=list[schemas.User])
@with_count_header(model=models.User)
async def read_users(
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
    """Get all users with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_users(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/settings", response_model=UserSettings)
def get_user_settings(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    """
    Get current user's settings.

    Returns the user's preferences including model defaults, UI settings,
    notifications, localization, editor, and privacy preferences.
    """
    # Query from database to ensure fresh data
    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return db_user.user_settings


@router.patch("/settings", response_model=UserSettings)
@handle_database_exceptions(entity_name="user settings")
def update_user_settings(
    settings_update: UserSettingsUpdate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    """
    Update user settings with partial data (deep merge).

    Only send the fields you want to change. The update will be deep merged
    into existing settings, so you can update nested properties without
    replacing the entire settings object.

    Example request body to update generation model:
    {
        "models": {
            "generation": {
                "model_id": "550e8400-e29b-41d4-a716-446655440000",
                "temperature": 0.7
            }
        }
    }

    Example request body to update UI theme:
    {
        "ui": {
            "theme": "dark"
        }
    }
    """
    # Get the user from database
    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Convert Pydantic model to dict, excluding unset fields but keeping explicit nulls, with UUIDs as strings
    # exclude_unset=True: Only include fields that were explicitly provided in the request
    # exclude_none=False (default): Keep fields that were explicitly set to null (for clearing values)
    settings_dict = settings_update.model_dump(exclude_unset=True, mode="json")

    # Get the settings manager instance (property creates new instance each time!)
    settings_manager = db_user.settings

    # Update settings using the centralized manager (deep merge)
    settings_manager.update(settings_dict)

    # Persist changes back to the database column using the SAME manager instance
    db_user.user_settings = settings_manager.raw

    # Flag the JSONB column as modified so SQLAlchemy tracks the change
    flag_modified(db_user, "user_settings")

    # Transaction commit is handled automatically by get_tenant_db_session context manager

    logger.info(f"Updated settings for user {db_user.email}")

    return db_user.user_settings


@router.get("/{user_id}", response_model=schemas.User)
def read_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id_tenant = tenant_context
    db_user = crud.get_user(
        db, user_id=user_id, organization_id=organization_id, tenant_user_id=user_id_tenant
    )
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.delete("/{user_id}", response_model=schemas.User)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id_tenant = tenant_context

    try:
        db_user = crud.delete_user(
            db, target_user_id=user_id, organization_id=organization_id, user_id=user_id_tenant
        )
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        return db_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/leave-organization", response_model=schemas.User)
def leave_organization(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    """
    Allow a user to leave their current organization.

    This sets the user's organization_id to NULL, removing them from their organization.
    The user account remains active but loses organization access.
    On next login, the user will go through the onboarding flow again.

    The user is identified by their authentication token.
    """
    # Check if user is part of an organization
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=400, detail="You are not currently part of any organization"
        )

    # Get the user from the database
    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Store organization name for logging
    organization = None
    if db_user.organization_id:
        organization = (
            db.query(models.Organization)
            .filter(models.Organization.id == db_user.organization_id)
            .first()
        )

    # Remove user from organization
    db_user.organization_id = None
    db.commit()
    db.refresh(db_user)

    # Log the action
    org_name = organization.name if organization else "Unknown"
    logger.info(f"User {db_user.email} left organization {org_name}")

    return db_user


@router.put("/{user_id}", response_model=schemas.User)
@handle_database_exceptions(
    entity_name="user", custom_unique_message="User with this email already exists"
)
def update_user(
    user_id: uuid.UUID,
    user: schemas.UserUpdate,
    request: Request,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    # Get optional tenant context - may be None during onboarding
    organization_id = str(current_user.organization_id) if current_user.organization_id else None
    user_id_tenant = str(current_user.id) if current_user.id else None

    # Get user with organization filtering (SECURITY CRITICAL)
    # During onboarding, organization_id may be None, which is acceptable
    db_user = crud.get_user(
        db, user_id=user_id, organization_id=organization_id, tenant_user_id=user_id_tenant
    )
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found or not accessible")

    # Only allow users to update their own profile or superusers to update any profile
    if str(db_user.id) != str(current_user.id) and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this user")

    # Update the user
    updated_user = crud.update_user(db, user_id=user_id, user=user)

    # If this is the current user being updated, refresh their session token
    if str(updated_user.id) == str(current_user.id):
        new_session_token = create_session_token(updated_user)
        return JSONResponse(
            content={
                "user": schemas.User.model_validate(updated_user).model_dump(mode="json"),
                "session_token": new_session_token,
            }
        )

    return updated_user

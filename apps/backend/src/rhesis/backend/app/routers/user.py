import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.auth_utils import (
    require_current_user_or_token,
    require_current_user_or_token_without_context,
)
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.auth import create_session_token
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.notifications import email_service

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token_without_context)],
)


@router.post("/", response_model=schemas.User)
async def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    # Set the organization_id from the current user
    user.organization_id = current_user.organization_id
    
    # Extract send_invite flag before creating user (since it's not part of the model)
    send_invite = user.send_invite
    
    # Remove send_invite from user data before creating user (it's not part of the database model)
    user_data = user.model_copy(exclude={'send_invite'})
    
    # Create the user
    created_user = crud.create_user(db=db, user=user_data)
    
    # Send invitation email if requested
    if send_invite and email_service.is_configured:
        try:
            logger.info(f"Sending invitation email to {created_user.email}")
            
            # Get organization information for the email
            organization = None
            if current_user.organization_id:
                organization = db.query(models.Organization).filter(
                    models.Organization.id == current_user.organization_id
                ).first()
            
            organization_name = organization.name if organization else "Your Organization"
            organization_website = organization.website if organization else None
            inviter_name = current_user.name or f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or "Team Member"
            
            # Send the invitation email
            success = email_service.send_team_invitation_email(
                recipient_email=created_user.email,
                recipient_name=created_user.name or created_user.given_name,
                organization_name=organization_name,
                organization_website=organization_website,
                inviter_name=inviter_name,
                inviter_email=current_user.email
            )
            
            if success:
                logger.info(f"Successfully sent invitation email to {created_user.email}")
            else:
                logger.warning(f"Failed to send invitation email to {created_user.email}")
                
        except Exception as e:
            logger.error(f"Error sending invitation email to {created_user.email}: {str(e)}")
            # Don't fail user creation if email sending fails
    
    return created_user


@router.post("/test-invitation")
async def test_invitation_email(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token)
):
    """
    Test endpoint to send a sample invitation email.
    Creates a temporary user with send_invite=True to test the email functionality.
    """
    try:
        # Create a test user with send_invite=True
        test_user_data = schemas.UserCreate(
            email=f"test-invite-{uuid.uuid4().hex[:8]}@example.com",
            name="Test Invitation User",
            given_name="Test",
            family_name="User",
            is_active=True,
            organization_id=current_user.organization_id,
            send_invite=True
        )
        
        # Extract send_invite and create user data without it
        send_invite = test_user_data.send_invite
        user_data_for_db = test_user_data.model_copy(exclude={'send_invite'})
        
        # Create the user
        created_user = crud.create_user(db=db, user=user_data_for_db)
        
        # Send invitation email if requested
        if send_invite and email_service.is_configured:
            try:
                # Get organization information
                organization = None
                if current_user.organization_id:
                    organization = db.query(models.Organization).filter(
                        models.Organization.id == current_user.organization_id
                    ).first()
                
                organization_name = organization.name if organization else "Test Organization"
                organization_website = organization.website if organization else None
                inviter_name = current_user.name or f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or "Test User"
                
                # Send the invitation email
                email_service.send_team_invitation_email(
                    recipient_email=created_user.email,
                    recipient_name=created_user.name or created_user.given_name,
                    organization_name=organization_name,
                    organization_website=organization_website,
                    inviter_name=inviter_name,
                    inviter_email=current_user.email
                )
            except Exception as e:
                logger.error(f"Error sending test invitation email: {str(e)}")
        
        # Clean up - delete the test user
        db.delete(created_user)
        db.commit()
        
        return {
            "success": True,
            "message": f"Test invitation email sent to {test_user_data.email}",
            "test_email": test_user_data.email
        }
        
    except Exception as e:
        logger.error(f"Error in test invitation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Test invitation failed: {str(e)}"
        )


@router.get("/", response_model=list[schemas.User])
@with_count_header(model=models.User)
async def read_users(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all users with their related objects"""
    return crud.get_users(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{user_id}", response_model=schemas.User)
def read_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user belongs to the same organization
    if db_user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this user")
    return db_user


@router.delete("/{user_id}", response_model=schemas.Behavior)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete users")

    # Get user before deletion to check organization
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user belongs to the same organization (even for superusers)
    if db_user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete users from other organizations"
        )

    return crud.delete_user(db, user_id=user_id)


@router.put("/{user_id}", response_model=schemas.User)
def update_user(
    user_id: uuid.UUID,
    user: schemas.UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    # Get user directly without RLS
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

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

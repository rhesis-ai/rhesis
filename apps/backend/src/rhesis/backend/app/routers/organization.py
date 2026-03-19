import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import (
    require_current_user_or_token,
    require_current_user_or_token_without_context,
)
from rhesis.backend.app.database import set_session_variables
from rhesis.backend.app.dependencies import (
    get_db_session,
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.organization import (
    execute_initial_test_runs,
    load_initial_data,
    rollback_initial_data,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.notifications import email_service

logger = logging.getLogger(__name__)


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

        default_model_ids = load_initial_data(db, str(organization_id), str(current_user.id))

        # Update user settings with the default models for generation, evaluation, and embedding
        if default_model_ids:
            # Get the user to update settings
            user = db.query(models.User).filter(models.User.id == current_user.id).first()
            if user:
                # Settings are auto-persisted when using user.settings
                user.settings.update(
                    {
                        "models": {
                            "generation": {"model_id": default_model_ids.get("language_model_id")},
                            "evaluation": {"model_id": default_model_ids.get("language_model_id")},
                            "embedding": {"model_id": default_model_ids.get("embedding_model_id")},
                        }
                    }
                )
                db.flush()

        # Mark onboarding as completed and commit while session variables are
        # still valid on the original connection. execute_initial_test_runs must
        # come AFTER this commit because it calls db.commit() internally, which
        # causes SQLAlchemy to release the connection back to the pool. The new
        # connection checked out afterwards would no longer have
        # app.current_organization set, causing the RLS UPDATE to match 0 rows.
        org.is_onboarding_complete = True

        db.commit()

        # Re-apply tenant session variables on the connection now held by the
        # session. db.commit() releases the connection back to the pool in
        # SQLAlchemy 2.x; the next operation checks out a fresh connection that
        # has no app.current_organization set. Without this, any RLS-protected
        # query inside execute_initial_test_runs would run without tenant context.
        set_session_variables(db, str(organization_id), str(current_user.id))

        # Execute initial test runs after the org is marked complete.
        # This is non-blocking - if it fails, onboarding has already succeeded.
        test_execution_summary = None
        try:
            test_execution_summary = execute_initial_test_runs(
                db=db, organization_id=str(organization_id), user_id=str(current_user.id)
            )
        except Exception as test_exec_error:
            logger.warning("Initial test execution failed: %s", test_exec_error)
            test_execution_summary = {
                "status": "error",
                "message": (
                    f"Test execution failed but onboarding completed: {str(test_exec_error)}"
                ),
                "submitted": 0,
                "failed": 0,
                "test_set_count": 0,
                "endpoint_count": 0,
            }

        # Prepare response after successful commit
        response = {
            "status": "success",
            "message": "Initial data loaded successfully",
            "default_model_ids": default_model_ids,
            "test_execution": test_execution_summary,
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("load-initial-data failed for org_id=%s", organization_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize organization data: {str(e)}"
        )

    # Schedule onboarding emails AFTER successful DB commit
    print(
        f"\n{'=' * 70}\n"
        f"  🚀  Onboarding complete — scheduling Day 1/2/3 emails\n"
        f"      Recipient : {current_user.email}\n"
        f"      Name      : {current_user.name or current_user.given_name or '(none)'}\n"
        f"      Org ID    : {organization_id}\n"
        f"{'=' * 70}\n"
    )

    email_schedule = [
        (1, email_service.send_day_1_email),
        (2, email_service.send_day_2_email),
        (3, email_service.send_day_3_email),
    ]

    email_results = {}
    for day, send_method in email_schedule:
        try:
            success = send_method(
                recipient_email=current_user.email,
                recipient_name=current_user.name or current_user.given_name,
            )
            email_results[f"day_{day}"] = "scheduled" if success else "skipped"
            if not success:
                logger.warning(
                    f"Day {day} email not sent for {current_user.email} (check configuration)"
                )
                print(
                    f"⚠️  [ONBOARDING] Day {day} email was NOT scheduled for "
                    f"{current_user.email} — check SENDGRID_API_KEY and "
                    f"SENDGRID_DAY_{day}_EMAIL_TEMPLATE_ID env vars."
                )
        except Exception:
            email_results[f"day_{day}"] = "error"
            logger.exception(f"Failed to schedule Day {day} email for {current_user.email}")
            print(
                f"❌  [ONBOARDING] Exception scheduling Day {day} email for "
                f"{current_user.email} — see traceback above."
            )

    print(f"\n  📊  Email scheduling results: {email_results}\n{'=' * 70}\n")

    response["email_schedule"] = email_results
    return response


@router.post("/{organization_id}/trigger-test-emails", response_model=dict)
async def trigger_test_onboarding_emails(
    organization_id: uuid.UUID,
    simulate: bool = Query(False, description="Log payload only; skip actual SendGrid API call"),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Trigger test onboarding emails with short minute-based delays.

    Day 1 → sent in 1 minute, Day 2 → sent in 2 minutes, Day 3 → sent in 3 minutes.
    Pass ?simulate=true to log the full SendGrid payload without actually calling the API.
    Intended for development/debugging only — bypasses the is_onboarding_complete lock.
    """
    org = crud.get_organization(db, organization_id=organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    mode_label = " [SIMULATE — no emails will be sent]" if simulate else ""
    print(
        f"\n{'=' * 70}\n"
        f"  🧪  Test email trigger{mode_label}\n"
        f"      Day 1/2/3 with 1/2/3-minute delays\n"
        f"      Recipient : {current_user.email}\n"
        f"      Name      : {current_user.name or current_user.given_name or '(none)'}\n"
        f"      Org ID    : {organization_id}\n"
        f"{'=' * 70}\n"
    )

    test_schedule = [(1, 1), (2, 2), (3, 3)]

    results = {}
    for day, delay_minutes in test_schedule:
        try:
            success = email_service.send_test_onboarding_email(
                day=day,
                recipient_email=current_user.email,
                recipient_name=current_user.name or current_user.given_name,
                delay_minutes=delay_minutes,
                simulate=simulate,
            )
            results[f"day_{day}"] = (
                "simulated" if (simulate and success) else ("scheduled" if success else "skipped")
            )
            if not success:
                logger.warning(
                    "Test Day %d email not scheduled for %s "
                    "(check SENDGRID_API_KEY and SENDGRID_DAY_%d_EMAIL_TEMPLATE_ID)",
                    day,
                    current_user.email,
                    day,
                )
        except Exception:
            results[f"day_{day}"] = "error"
            logger.exception("Failed to schedule test Day %d email for %s", day, current_user.email)

    print(f"\n  📊  Test email results: {results}\n{'=' * 70}\n")

    message = (
        "Simulated: payload logged, no emails sent. Day 1/2/3 templates shown above."
        if simulate
        else "Test emails triggered: Day 1 in 1 min, Day 2 in 2 min, Day 3 in 3 min"
    )
    return {
        "status": "ok",
        "message": message,
        "recipient": current_user.email,
        "simulate": simulate,
        "results": results,
    }


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

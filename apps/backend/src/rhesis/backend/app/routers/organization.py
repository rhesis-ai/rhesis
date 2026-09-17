import logging
import uuid

import anyio
from fastapi import Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import authorize
from rhesis.backend.app.auth.user_utils import (
    require_current_user_or_token,
    require_current_user_or_token_without_context,
)
from rhesis.backend.app.crud import organization as organization_crud
from rhesis.backend.app.database import set_session_variables
from rhesis.backend.app.dependencies import (
    OffLoopSession,
    get_db_session,
    get_off_loop_tenant_session,
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.error_handlers import internal_error
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.services import organization_branding as branding_service
from rhesis.backend.app.services.organization import (
    execute_initial_test_runs,
    load_initial_data,
    rollback_initial_data,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.notifications import email_service

logger = logging.getLogger(__name__)


router = RhesisRouter(
    prefix="/organizations",
    tags=["organizations"],
    responses={404: {"description": "Not found"}},
    resource="organization",
)


@router.post("/", response_model=schemas.Organization)
@handle_database_exceptions(
    entity_name="organization", custom_unique_message="Organization with this name already exists"
)
def create_organization(
    organization: schemas.OrganizationCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    # owner_id and user_id are always set server-side from the authenticated caller —
    # the client-supplied values are ignored so the onboarding flow cannot forge ownership.
    return organization_crud.create_organization(
        db=db, organization=organization, owner_user_id=current_user.id
    )


@router.get("/", response_model=list[schemas.Organization])
@with_count_header(model=models.Organization)
def read_organizations(
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
        return organization_crud.get_organizations(
            db=db,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
            organization_id=organization_id,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Organization settings — the org-level mirror of GET/PATCH /users/settings.
#
# These must stay ABOVE the "/{organization_id}" routes below: FastAPI matches
# in declaration order, so a later literal path loses to an earlier parameter
# and "settings" would be parsed as a UUID.
# ---------------------------------------------------------------------------


def _current_organization(db: Session, organization_id) -> models.Organization:
    """Load the caller's own organization, or 404."""
    org = db.query(models.Organization).filter(models.Organization.id == organization_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _settings_permitted_actions(request: Request, current_user: User, db: Session) -> list[str]:
    """Resolve which settings actions the caller may take, for the UI's affordances."""
    principal = resolve_principal_from_request(current_user, request)
    actions: list[str] = []
    if authorize(principal, Permission.Organization.UPDATE, project_id=None, db=db):
        actions.append(str(Permission.Organization.UPDATE))
    return actions


def _persist_settings(db: Session, org: models.Organization, updates: dict) -> dict:
    """Deep-merge ``updates`` into the org's settings and flag the JSONB column."""
    manager = org.settings
    manager.update(updates)
    org.organization_settings = manager.raw
    # Without this SQLAlchemy does not see the in-place mutation of the JSONB value.
    flag_modified(org, "organization_settings")
    return org.organization_settings


# The branding handlers below are ``async`` because they await file reads and,
# for a Google font, an outbound HTTP check. That puts them on the event loop,
# where a psycopg2 call would block every other request in the worker — so they
# take an ``OffLoopSession`` and reach it only through these helpers, which hop
# to the threadpool. Each helper does all its DB work in a single
# ``run_sync`` call so the Session never crosses thread boundaries.
# See tests/backend/test_no_sync_db_on_loop.py.


async def _read_and_apply_branding(
    db: OffLoopSession,
    organization_id,
    updates: dict,
    read_key: str | None = None,
) -> tuple[dict | None, dict]:
    """Read the previous branding (optionally), apply updates and commit.

    Returns ``(previous_value, new_settings)``.  When ``read_key`` is given the
    previous value is ``branding[read_key]`` (e.g. ``"font"`` or ``"favicon"``);
    otherwise ``previous`` is ``None``.

    Everything runs in one thread hop so the Session is never used from two
    different threads.
    """

    def _do() -> tuple[dict | None, dict]:
        previous = None
        if read_key is not None:
            branding = dict(_current_organization(db, organization_id).settings.branding.all)
            previous = branding.get(read_key)

        org = _current_organization(db, organization_id)
        settings = _persist_settings(db, org, updates)
        db.commit()
        return previous, settings

    return await anyio.to_thread.run_sync(_do)


async def _apply_branding(db: OffLoopSession, organization_id, updates: dict) -> dict:
    """Apply updates without reading previous state. Convenience wrapper."""
    _, settings = await _read_and_apply_branding(db, organization_id, updates)
    return settings


@router.get(
    "/settings",
    response_model=schemas.OrganizationSettingsRead,
    **capability(Permission.Organization.READ),
)
def get_organization_settings(
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get the calling user's organization settings (branding, and future sections)."""
    organization_id, _ = tenant_context
    org = _current_organization(db, organization_id)

    return {
        **(org.organization_settings or {"version": 1, "branding": {}}),
        "permitted_actions": _settings_permitted_actions(request, current_user, db),
    }


@router.patch(
    "/settings",
    response_model=schemas.OrganizationSettings,
    **capability(Permission.Organization.UPDATE),
)
@handle_database_exceptions(entity_name="organization settings")
async def update_organization_settings(
    settings_update: schemas.OrganizationSettingsUpdate,
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update organization settings with partial data (deep merge).

    Send only the fields you want to change. An explicit ``null`` clears a
    field, which is how branding reverts to the deployment-wide ``BRAND_*``
    env var and then to the Rhesis default.

    ``branding.font`` accepts a Google family here because that is pure
    configuration. Uploading font files is multipart, so it keeps its own
    endpoint.
    """
    organization_id, _ = tenant_context

    # exclude_unset keeps untouched fields alone; exclude_none stays off so an
    # explicit null still clears.
    updates = settings_update.model_dump(exclude_unset=True, mode="json")
    # `{"branding": null}` has no meaning — a section is not a value, and every
    # field inside it clears individually. Dropping it here keeps the response
    # model, whose `branding` is non-optional, from rejecting what we stored.
    if updates.get("branding", {}) is None:
        del updates["branding"]
    branding_update = updates.get("branding") or {}
    font_touched = "font" in branding_update
    new_font = branding_update.get("font")

    if new_font:
        await branding_service.verify_google_font(new_font["family"])
        # Dump the full descriptor, not just the two fields the caller sent.
        # Settings are deep merged, so a partial font dict would blend with
        # whatever an earlier upload left behind and keep its slug and weights.
        branding_update["font"] = schemas.BrandingFont(
            source="google", family=new_font["family"]
        ).model_dump()

    # Switching to a Google font, or clearing the font, strands whatever files
    # a previous upload left in storage.
    previous_font, result = await _read_and_apply_branding(
        db, organization_id, updates, read_key="font" if font_touched else None
    )

    if previous_font and previous_font.get("source", "upload") == "upload":
        await branding_service.delete_font(str(organization_id), previous_font)

    logger.info(f"Updated settings for organization {organization_id}")
    return result


@router.post(
    "/settings/branding/favicon",
    response_model=schemas.OrganizationSettings,
    **capability(Permission.Organization.UPDATE),
)
async def upload_branding_favicon(
    file: UploadFile = File(...),
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Upload the organization's favicon, replacing any existing one."""
    organization_id, _ = tenant_context

    descriptor = await branding_service.upload_favicon(str(organization_id), file)

    previous, result = await _read_and_apply_branding(
        db, organization_id, {"branding": {"favicon": descriptor.model_dump()}}, read_key="favicon"
    )

    # Only after the new descriptor is persisted, and only when the path
    # actually changed — re-uploading the same type overwrites in place, so
    # deleting the old path would delete the new file.
    if previous and previous.get("path") != descriptor.path:
        await branding_service.delete_favicon(previous)

    return result


# The favicon keeps a DELETE because it cannot be cleared through PATCH: it is
# a storage descriptor, and BrandingSettingsUpdate deliberately cannot express
# one. A font can (``font: null``), so it needs no DELETE of its own.
@router.delete(
    "/settings/branding/favicon",
    response_model=schemas.OrganizationSettings,
    **capability(Permission.Organization.UPDATE),
)
async def delete_branding_favicon(
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Clear the organization's favicon, reverting to BRAND_FAVICON_URL or the Rhesis icon."""
    organization_id, _ = tenant_context

    previous, result = await _read_and_apply_branding(
        db, organization_id, {"branding": {"favicon": None}}, read_key="favicon"
    )
    await branding_service.delete_favicon(previous)
    return result


@router.post(
    "/settings/branding/font",
    response_model=schemas.OrganizationSettings,
    **capability(Permission.Organization.UPDATE),
)
async def upload_branding_font(
    family: str = Form(...),
    weight_300: UploadFile | None = File(None),
    weight_400: UploadFile | None = File(None),
    weight_700: UploadFile | None = File(None),
    db: OffLoopSession = Depends(get_off_loop_tenant_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Upload the organization's brand font. At least one weight is required."""
    organization_id, _ = tenant_context

    descriptor = await branding_service.upload_font(
        str(organization_id),
        family,
        {"300": weight_300, "400": weight_400, "700": weight_700},
    )

    previous, result = await _read_and_apply_branding(
        db, organization_id, {"branding": {"font": descriptor.model_dump()}}, read_key="font"
    )

    # A renamed family writes to a new slug, orphaning every old file; keeping
    # the family but uploading fewer weights orphans just the dropped ones.
    if previous and previous.get("source", "upload") == "upload":
        # Spare a weight only when the new file overwrote the old one in place.
        # Re-uploading 400 as .woff2 over a .ttf writes a different filename, so
        # the .ttf still has to go.
        keep = None
        if previous.get("slug") == descriptor.slug:
            previous_extensions = previous.get("extensions") or {}
            keep = {
                weight
                for weight, extension in descriptor.extensions.items()
                if previous_extensions.get(weight) == extension
            }
        await branding_service.delete_font(str(organization_id), previous, keep_weights=keep)

    return result


@router.get(
    "/settings/branding/google-fonts",
    response_model=list[str],
    **capability(Permission.Organization.READ),
)
def list_google_font_families(
    current_user: User = Depends(require_current_user_or_token),
):
    """Family names published on Google Fonts, for the branding form's picker.

    Fetched from Google and cached in-process for a day. Answers an empty list
    when the catalogue is unreachable rather than failing: the family field
    accepts free text either way, and the name is verified against Google on
    save.
    """
    return branding_service.list_google_fonts()


@router.get(
    "/settings/branding/assets/{asset}",
    **capability(Permission.Organization.READ),
)
def get_branding_asset(
    request: Request,
    asset: str,
    slug: str | None = Query(
        None, description="Font slug the caller's @font-face asked for; 404s on mismatch"
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Serve a stored branding asset to the caller's own organization.

    ``asset`` is ``favicon`` or ``font-{weight}``. The organization comes from
    the tenant context, never the path, so one org cannot read another's assets.
    The frontend's ``/brand-assets`` and ``/brand-fonts`` routes proxy here.
    """
    organization_id, _ = tenant_context
    org = _current_organization(db, organization_id)
    branding = org.settings.branding

    if asset == "favicon":
        content, content_type, sha256 = branding_service.read_favicon(branding.favicon)
    elif asset.startswith("font-"):
        content, content_type, sha256 = branding_service.read_font_weight(
            str(organization_id), branding.font, asset[len("font-") :], expected_slug=slug
        )
    else:
        raise HTTPException(status_code=404, detail="Unknown branding asset")

    headers = branding_service.asset_response_headers(content_type, sha256)

    # The frontend proxy forwards If-None-Match on the unversioned URL, which
    # is revalidated rather than immutable. Without this the body is re-sent on
    # every check.
    if sha256 and request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)

    return Response(content=content, headers=headers)


@router.get("/{organization_id}", response_model=schemas.Organization)
def read_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        tenant_organization_id, user_id = tenant_context
        db_organization = organization_crud.get_organization(
            db,
            organization_id=organization_id,
            tenant_organization_id=tenant_organization_id,
            user_id=user_id,
        )
        if db_organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        return db_organization
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
    db_organization = organization_crud.update_organization(
        db, organization_id=organization_id, organization=organization
    )
    if db_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return db_organization


@router.post(
    "/{organization_id}/load-initial-data",
    response_model=dict,
    **capability(Permission.Organization.UPDATE),
)
def initialize_organization_data(
    organization_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Load initial data for an organization if onboarding is not complete."""
    try:
        org = organization_crud.get_organization(db, organization_id=organization_id)
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

        # Assign the org creator the Owner role (EE). The handler resolves Owner
        # vs Member from organization.owner_id, so the creator (owner_id ==
        # current_user.id) becomes Owner. No-op in community builds / RBAC-off.
        # Runs here (not at org creation) because tenant GUCs are valid only
        # after set_session_variables, which organization_member RLS requires.
        from rhesis.backend.app.auth.org_membership_hook import on_user_org_assigned

        on_user_org_assigned(db, current_user.id, organization_id)

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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise internal_error(
            e, context=f"loading initial data for organization {organization_id}"
        ) from e

    # Schedule onboarding emails AFTER successful DB commit
    logger.info("Onboarding complete — scheduling Day 1/2/3 emails for org_id=%s", organization_id)

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
                    "Day %s email not scheduled for org_id=%s — check SENDGRID_API_KEY "
                    "and SENDGRID_DAY_%s_EMAIL_TEMPLATE_ID env vars.",
                    day,
                    organization_id,
                    day,
                )
        except Exception:
            email_results[f"day_{day}"] = "error"
            logger.exception("Failed to schedule Day %s email for org_id=%s", day, organization_id)

    logger.info("Email scheduling results for org_id=%s: %s", organization_id, email_results)
    response["email_schedule"] = email_results
    return response


@router.post(
    "/{organization_id}/rollback-initial-data",
    response_model=dict,
    **capability(Permission.Organization.UPDATE),
)
def rollback_organization_data(
    organization_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Rollback initial data for an organization."""
    try:
        print(f"Rolling back initial data for organization {organization_id}")
        org = organization_crud.get_organization(db, organization_id=organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        if not org.is_onboarding_complete:
            raise HTTPException(status_code=400, detail="Organization not initialized yet")

        rollback_initial_data(db, str(organization_id), str(current_user.id))

        # Mark onboarding as incomplete
        org.is_onboarding_complete = False
        # Transaction commit is handled by the session context manager

        return {"status": "success", "message": "Initial data rolled back successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

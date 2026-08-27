"""CRUD operations for organizations.

``create_organization`` is the one function here that steps outside the normal tenant
machinery. Every other entity is created *inside* a tenant, so the org/user GUCs are
already set and RLS applies; an organization *is* the tenant, so there is nothing to scope
it to yet. It therefore calls ``reset_session_context`` to blank those GUCs, expires the
session so no already-loaded row drags a stale tenant context along, and returns the
flushed object without a refresh -- the refresh is what typically trips RLS here.

``get_session_variables`` lives in this module because ``create_organization`` is its only
caller: it reads back ``app.current_organization``/``app.current_user`` before and after
that reset so the debug log shows the GUCs really were cleared.
"""

import logging
import uuid
from typing import List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.database import reset_session_context
from rhesis.backend.app.utils.crud_utils import (
    delete_item,
    get_item,
    get_items,
    update_item,
)

logger = logging.getLogger(__name__)


# Helper function to print session variables
def get_session_variables(db: Session):
    """Get and return the current PostgreSQL session variables for debugging"""
    results = {}
    try:
        # Check if variables exist before trying to show them
        check_org = db.execute(
            text("SELECT current_setting('app.current_organization', true)")
        ).scalar()
        check_user = db.execute(text("SELECT current_setting('app.current_user', true)")).scalar()

        results["app.current_organization"] = check_org if check_org else "Not set"
        results["app.current_user"] = check_user if check_user else "Not set"

        return results
    except Exception as e:
        logger.debug(f"Error getting session variables: {e}")
        return {"error": str(e)}


def get_organization(
    db: Session, organization_id: uuid.UUID, tenant_organization_id: str = None, user_id: str = None
) -> Optional[models.Organization]:
    """Get organization."""
    return get_item(db, models.Organization, organization_id, tenant_organization_id, user_id)


def get_organizations(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Organization]:
    return get_items(
        db,
        models.Organization,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_organization(
    db: Session,
    organization: schemas.OrganizationCreate,
    owner_user_id: Optional[UUID] = None,
) -> models.Organization:
    """Create a new organization without RLS checks, because we're creating a new organization.

    When *owner_user_id* is supplied (always the case on the HTTP path) it overrides any
    client-supplied ``owner_id``/``user_id`` values in the schema, making the backend
    authoritative for org ownership (SP3 decision — server-set, cannot be forged).
    Internal callers such as ``local_init.py`` that already supply the correct IDs in the
    schema may pass ``owner_user_id=None`` to preserve the existing behaviour.
    """
    # Print session variables before reset
    before_vars = get_session_variables(db)
    logger.info(f"Session variables BEFORE reset: {before_vars}")

    # Reset session context to ensure the new organization is created correctly
    reset_session_context(db)

    # Verify variables are cleared
    after_vars = get_session_variables(db)
    logger.info(f"Session variables AFTER reset: {after_vars}")

    # Make sure session is clean to avoid RLS issues
    db.expire_all()

    # Convert Pydantic model to dict; project_id is not a column on Organization
    org_data = organization.model_dump(exclude={"project_id"})

    # Backend is authoritative for ownership when owner_user_id is provided.
    if owner_user_id is not None:
        org_data["owner_id"] = str(owner_user_id)
        org_data["user_id"] = str(owner_user_id)

    db_org = models.Organization(**org_data)

    # Add to session - transaction management is handled by context manager
    db.add(db_org)
    db.flush()  # Flush to get the ID

    # Simply return the object without refreshing
    # The refresh operation is what often triggers RLS issues
    logger.info(f"Organization created successfully: {db_org.id}")
    return db_org


def update_organization(
    db: Session, organization_id: uuid.UUID, organization: schemas.OrganizationUpdate
) -> Optional[models.Organization]:
    return update_item(db, models.Organization, organization_id, organization)


def delete_organization(db: Session, organization_id: uuid.UUID) -> Optional[models.Organization]:
    """Delete organization - requires superuser permissions (handled in router)"""
    return delete_item(db, models.Organization, organization_id)

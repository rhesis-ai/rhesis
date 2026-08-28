"""CRUD operations for users.

Users are the one entity that regularly exists *outside* an organization, so most of these
functions deliberately sidestep the tenant machinery the rest of ``crud`` relies on.
``create_user`` builds the ``User`` row directly instead of going through ``create_item``
because a user being invited or signing up has no ``organization_id`` yet and the
org-filtered helpers would reject it; ``update_user`` queries by primary key with no
organization filter for the same reason -- it is what the onboarding flow uses to attach a
brand-new user to the org it just created. ``get_user_by_email`` and ``get_user_by_id``
are likewise unfiltered: they are the auth lookups that run *before* a tenant context
exists, which is why they take no ``organization_id``. Everything that runs with a tenant
context (``get_user``, ``get_users``, ``delete_user``) does apply the filter.

``delete_user`` deletes nothing. It removes a user from their organization by nulling
``organization_id``; the account and all its data survive and the user lands back in the
onboarding flow on next login. Three things happen on the way, and their order is
load-bearing:

- It refuses to act when the target is the caller, so an admin cannot lock themselves out
  of the org they administer.
- It drops the user's ``ProjectMembership`` rows for the org first, inside
  ``bypass_tenant_filter()``. Those rows can only be found through the org FK, so the
  query has to run while ``organization_id`` is still set -- nulling it first would strand
  them.
- It clears ``default_project`` from the user's settings, which points at a project in the
  org being left and would otherwise be dangling on their next session.

Two lookup quirks worth knowing before calling them: ``get_user_by_email`` compares with
``func.lower()`` on both sides, so it matches regardless of how the address was cased at
signup, and ``get_user_by_id`` returns ``None`` for a malformed UUID string rather than
raising -- a caller cannot tell "no such user" from "that wasn't a UUID".
"""

import uuid
from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.org_membership_hook import on_user_org_assigned
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.app.utils.crud_utils import get_item, get_items


def get_user(
    db: Session, user_id: uuid.UUID, organization_id: str = None, tenant_user_id: str = None
) -> Optional[models.User]:
    """Get user."""
    return get_item(db, models.User, user_id, organization_id, tenant_user_id)


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.User]:
    return get_items(
        db,
        models.User,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Create a new user without RLS checks, because we're creating a new user that has no
    organization_id"""
    # Exclude fields not present on the User model
    user_data = user.model_dump(exclude={"send_invite", "project_id"})
    db_user = models.User(**user_data)
    db.add(db_user)
    # Flush to get ID and other generated values before refresh
    db.flush()

    # Seed the default org-role (EE) so the user is not locked out once RBAC is
    # enabled for their org. No-op in community builds / when no org is set.
    if db_user.organization_id is not None:
        on_user_org_assigned(db, db_user.id, db_user.organization_id)

    # Transaction commit is handled by the session context manager
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: uuid.UUID, user: schemas.UserUpdate) -> Optional[models.User]:
    """Update user with special handling for onboarding (no organization)"""
    # Direct query without RLS filters for user updates
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None

    # Update user attributes
    user_data = user.model_dump(exclude_unset=True)
    for key, value in user_data.items():
        setattr(db_user, key, value)

    # Transaction commit/rollback is handled by the session context manager
    return db_user


def delete_user(
    db: Session, target_user_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.User]:
    """
    Remove a user from their organization by setting organization_id to NULL.

    The user account remains active but loses organization access.
    This preserves the user account and all their data while removing
    organizational context. On next login, the user will go through
    the onboarding flow again.

    Also removes all project memberships within the org and clears
    default_project so no orphaned rows or stale settings remain.

    Args:
        db: Database session
        target_user_id: ID of user to remove from organization
        organization_id: Organization ID for tenant context
        user_id: ID of the current user performing the action (for tenant context)

    Returns:
        Updated user object or None if not found

    Raises:
        ValueError: If user tries to delete themselves
    """
    # Security check: Prevent users from deleting themselves
    if str(target_user_id) == str(user_id):
        raise ValueError("Users cannot remove themselves from the organization")

    # Get the user with tenant context
    db_user = get_item(db, models.User, target_user_id, organization_id, user_id)
    if db_user is None:
        return None

    # Drop all project memberships within this org before nulling organization_id,
    # while we can still identify them via the org FK.
    with bypass_tenant_filter():
        memberships = (
            db.query(ProjectMembership)
            .filter_by(user_id=target_user_id, organization_id=organization_id)
            .all()
        )
        for m in memberships:
            db.delete(m)

    # Clear default_project — it's org-scoped so it would be stale after removal.
    if db_user.settings.default_project is not None:
        settings = db_user.settings.raw.copy()
        settings.pop("default_project", None)
        db_user.user_settings = settings
        flag_modified(db_user, "user_settings")

    # Null the org FK last so the membership query above can still use it.
    db_user.organization_id = None

    db.commit()
    db.refresh(db_user)

    return db_user


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Look up a user by email, case-insensitively on both sides."""
    return db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()


def get_user_by_id(db: Session, user_id: Union[str, UUID]) -> Optional[models.User]:
    """Retrieve a user by their ID. Accepts both string and UUID.

    Returns None for a malformed UUID string rather than raising.
    """
    try:
        # Convert string to UUID if it's a string
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        return db.query(models.User).filter(models.User.id == user_id).first()
    except ValueError:
        # Handle invalid UUID string
        return None

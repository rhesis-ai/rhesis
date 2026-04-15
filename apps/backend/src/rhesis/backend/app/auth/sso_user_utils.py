"""Org-scoped SSO user resolution.

This is the critical security boundary for SSO. Unlike find_or_create_user_from_auth()
which matches users globally by email, this function enforces org scoping to prevent
cross-org account takeover.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.providers.base import AuthUser
from rhesis.backend.app.auth.sso_audit import SSOAuditEvent, audit_log
from rhesis.backend.app.schemas.sso_config import SSOConfig
from rhesis.backend.app.utils.validation import validate_and_normalize_email

logger = logging.getLogger(__name__)


class SSOLoginError(Exception):
    """Raised when SSO login is rejected.

    Contains a reason_code for audit logging but the caller should only
    expose a generic error to the user.
    """

    def __init__(self, reason_code: str, message: str = "SSO login failed"):
        self.reason_code = reason_code
        super().__init__(message)


def find_or_create_sso_user(
    db: Session,
    auth_user: AuthUser,
    organization,
    sso_config: SSOConfig,
):
    """Find or create a user via SSO with org-scoped resolution.

    Security invariants:
    1. Email is normalized before any lookup or domain check
    2. allowed_domains is enforced if configured
    3. User lookup is scoped to the authenticating org
    4. Users in other orgs are rejected (cross-org prevention)
    5. Auto-provisioning requires explicit opt-in

    Returns the User model instance on success.
    Raises SSOLoginError on any rejection.
    """
    from rhesis.backend.app.models.user import User
    from rhesis.backend.app.schemas import user as user_schemas
    from rhesis.backend.app import crud

    org_id = str(organization.id)

    # 1. Normalize email
    try:
        normalized_email = validate_and_normalize_email(auth_user.email)
    except ValueError:
        audit_log(
            SSOAuditEvent.USER_REJECTED,
            org_id,
            email=auth_user.email,
            reason_code="invalid_email",
        )
        raise SSOLoginError("invalid_email")

    # 2. Enforce allowed_domains
    if sso_config.allowed_domains:
        domain = normalized_email.rsplit("@", 1)[-1].lower()
        if domain not in sso_config.allowed_domains:
            audit_log(
                SSOAuditEvent.USER_REJECTED,
                org_id,
                email=normalized_email,
                reason_code="domain_not_allowed",
                details={"domain": domain},
            )
            raise SSOLoginError("domain_not_allowed")

    # 3. Look up user by email within the authenticating org
    user_in_org = (
        db.query(User)
        .filter(
            User.email == normalized_email,
            User.organization_id == organization.id,
            User.is_deleted.is_(False),
        )
        .first()
    )

    if user_in_org:
        current_time = datetime.now(timezone.utc)
        user_in_org.name = auth_user.name or user_in_org.name
        user_in_org.given_name = auth_user.given_name or user_in_org.given_name
        user_in_org.family_name = auth_user.family_name or user_in_org.family_name
        user_in_org.picture = auth_user.picture or user_in_org.picture
        user_in_org.provider_type = auth_user.provider_type
        user_in_org.external_provider_id = auth_user.external_id
        user_in_org.last_login_at = current_time
        user_in_org.is_email_verified = True
        return user_in_org

    # 4. Check if user exists in a different org (cross-org prevention)
    user_other_org = (
        db.query(User)
        .filter(
            User.email == normalized_email,
            User.is_deleted.is_(False),
        )
        .first()
    )

    if user_other_org:
        audit_log(
            SSOAuditEvent.USER_REJECTED,
            org_id,
            email=normalized_email,
            reason_code="cross_org_collision",
            details={"existing_org_id": str(user_other_org.organization_id)},
        )
        raise SSOLoginError("cross_org_collision")

    # 5. User doesn't exist anywhere
    if not sso_config.auto_provision_users:
        audit_log(
            SSOAuditEvent.USER_REJECTED,
            org_id,
            email=normalized_email,
            reason_code="auto_provision_disabled",
        )
        raise SSOLoginError("auto_provision_disabled")

    # 6. Auto-provision: create user in this org
    current_time = datetime.now(timezone.utc)
    user_data = user_schemas.UserCreate(
        email=normalized_email,
        name=auth_user.name,
        given_name=auth_user.given_name,
        family_name=auth_user.family_name,
        picture=auth_user.picture,
        provider_type=auth_user.provider_type,
        external_provider_id=auth_user.external_id,
        is_active=True,
        is_superuser=False,
        is_email_verified=True,
        last_login_at=current_time,
        organization_id=organization.id,
    )
    user = crud.create_user(db, user_data)

    audit_log(
        SSOAuditEvent.USER_PROVISIONED,
        org_id,
        email=normalized_email,
    )

    return user

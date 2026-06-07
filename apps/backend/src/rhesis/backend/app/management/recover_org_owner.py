"""Break-glass operator helper — reassign an organization's owner.

Imported by ``apps/backend/scripts/recover_org_owner.py``.  Kept here so tests
can import ``rhesis.backend.app.management.recover_org_owner.run()`` without
adding the scripts directory to the Python path.

See the script wrapper for full usage documentation.
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


def _validate_uuids(org_id: str, user_id: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Parse and validate both UUID arguments early, before touching the DB."""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        logger.error("org_id is not a valid UUID: %r", org_id)
        sys.exit(1)
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        logger.error("user_id is not a valid UUID: %r", user_id)
        sys.exit(1)
    return org_uuid, user_uuid


def run(
    org_id: str,
    user_id: str,
    *,
    dry_run: bool = False,
) -> None:
    """Reassign ``organization.owner_id`` to a given user UUID.

    Args:
        org_id:  UUID string of the target organization.
        user_id: UUID string of the user to become the new org owner.
        dry_run: When ``True``, log what WOULD change and roll back — no
                 DB mutation.

    Raises:
        SystemExit(1): On validation failure or unexpected error.
    """
    org_uuid, user_uuid = _validate_uuids(org_id, user_id)

    from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
    from rhesis.backend.app.models.organization import Organization
    from rhesis.backend.app.models.user import User
    from rhesis.backend.app.scope import bypass_tenant_filter

    session = SessionLocal()
    try:
        bind_scope_to_session(
            session,
            organization_id=str(org_uuid),
            user_id=str(user_uuid),
        )

        with bypass_tenant_filter():
            org: Optional[Organization] = (
                session.query(Organization).filter_by(id=org_uuid).first()
            )
            if org is None:
                logger.error("Organization %s not found.", org_uuid)
                sys.exit(1)

            user: Optional[User] = (
                session.query(User)
                .filter_by(id=user_uuid, organization_id=org_uuid)
                .first()
            )
            if user is None:
                logger.error(
                    "User %s does not exist or does not belong to organization %s.",
                    user_uuid,
                    org_uuid,
                )
                sys.exit(1)

            previous_owner_id: Optional[uuid.UUID] = org.owner_id

            logger.info("Organization  : %s (%s)", org.name, org_uuid)
            logger.info(
                "Current owner : %s",
                previous_owner_id if previous_owner_id else "<none>",
            )
            logger.info("New owner     : %s (%s)", user.email, user_uuid)

            if previous_owner_id and str(previous_owner_id) == str(user_uuid):
                logger.warning(
                    "The target user is ALREADY the org owner — nothing to do."
                )
                return

            if dry_run:
                logger.info(
                    "DRY RUN — would set organization.owner_id = %s for org %s.",
                    user_uuid,
                    org_uuid,
                )
                logger.info("Rolling back (dry run).")
                session.rollback()
                return

            org.owner_id = user_uuid
            session.flush()

        # Bust the permission cache for both the old and new owner so the
        # ownership change takes effect on the next authorize() call rather than
        # waiting out the TTL. Reuses the canonical helper (it swallows and logs
        # its own failures, so a cache outage never blocks recovery).
        from rhesis.backend.app.services.organization import _bust_permission_cache

        if previous_owner_id:
            _bust_permission_cache(previous_owner_id, org_uuid)
        _bust_permission_cache(user_uuid, org_uuid)

        session.commit()
        logger.info(
            "SUCCESS — organization %s owner reassigned: %s → %s",
            org_uuid,
            previous_owner_id,
            user_uuid,
        )

    except SystemExit:
        raise
    except Exception:
        logger.exception("Unexpected error — rolling back.")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()

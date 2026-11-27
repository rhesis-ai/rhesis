"""An organization's branding, read for the email sent to its members."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.organization import find_organization
from rhesis.backend.app.services.organization_branding import favicon_png
from rhesis.backend.notifications.email.brand import OrganizationBrand

logger = logging.getLogger(__name__)


def load_organization_brand(
    db: Session, organization_id: Optional[UUID | str]
) -> Optional[OrganizationBrand]:
    """The organization's branding, or ``None`` when it set none or it can't be read.

    Returns plain values, so the result can be handed to a background task.
    """
    try:
        organization = find_organization(db, organization_id)
        if organization is None:
            return None
        branding = organization.settings.branding
        brand = OrganizationBrand(
            product_name=branding.product_name,
            primary_color=branding.primary_color,
            secondary_color=branding.secondary_color,
            logo_png=favicon_png(branding.favicon) if branding.product_name else None,
        )
    except Exception:
        # Mail still goes out, as Rhesis.
        logger.warning("email branding failed for organization %s", organization_id, exc_info=True)
        return None
    return brand if brand != OrganizationBrand() else None

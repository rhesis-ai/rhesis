"""Who a report PDF is from: the organization's branding, as in the rest of the app.

The brand line takes the org's product name (or its name) and primary colour, and its
favicon goes in the page corner. Without any branding the PDF says Rhesis.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from rhesis.backend.app import models
from rhesis.backend.app.services.organization_branding import favicon_png

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PdfBrand:
    name: str = "Rhesis"
    # 6-digit hex, used for the brand line.
    color: str = "#0080af"
    # A PNG for the top-right corner of every page.
    logo: Optional[bytes] = None


DEFAULT_PDF_BRAND = PdfBrand()


def pdf_brand(organization: Optional[models.Organization]) -> PdfBrand:
    """The organization's branding; Rhesis when there is none or it can't be read."""
    if organization is None:
        return DEFAULT_PDF_BRAND
    try:
        branding = organization.settings.branding
        name = branding.product_name or organization.display_name or organization.name
        return PdfBrand(
            name=name or DEFAULT_PDF_BRAND.name,
            color=branding.primary_color or DEFAULT_PDF_BRAND.color,
            logo=favicon_png(branding.favicon),
        )
    except Exception:
        logger.exception("report PDF branding failed for organization %s", organization.id)
        return DEFAULT_PDF_BRAND

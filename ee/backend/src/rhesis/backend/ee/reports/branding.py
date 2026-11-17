"""The organization's own branding on report PDFs (Advanced reports).

Without the feature, core prints Rhesis branding. With it, the brand line takes the
org's product name and primary colour, and its favicon goes in the page corner.
"""

import io
import logging
from typing import Optional

from PIL import Image
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.services.organization_branding import read_favicon
from rhesis.backend.app.services.report.sections import DEFAULT_PDF_BRAND, PdfBrand

logger = logging.getLogger(__name__)

# ReportLab draws rasters; an SVG favicon is left out.
_RASTER_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/x-icon",
    "image/vnd.microsoft.icon",
}


def org_pdf_brand(db: Session, organization: models.Organization) -> Optional[PdfBrand]:
    if not FeatureRegistry.is_available(FeatureName.ADVANCED_REPORTS, organization):
        return None
    branding = organization.settings.branding
    name = branding.product_name or organization.display_name or organization.name
    return PdfBrand(
        name=name or DEFAULT_PDF_BRAND.name,
        color=branding.primary_color or DEFAULT_PDF_BRAND.color,
        logo=_logo_png(branding.favicon),
    )


def _logo_png(favicon: Optional[dict]) -> Optional[bytes]:
    if not favicon or favicon.get("content_type") not in _RASTER_TYPES:
        return None
    try:
        content, _, _ = read_favicon(favicon)
        with Image.open(io.BytesIO(content)) as image:
            out = io.BytesIO()
            image.convert("RGBA").save(out, format="PNG")
            return out.getvalue()
    except Exception:
        logger.warning("organization favicon could not be used on a report PDF", exc_info=True)
        return None

"""Who a report PDF is from: the organization's branding, as in the rest of the app.

The brand line takes the org's product name (or its name) and primary colour, and its
favicon goes in the page corner. Without any branding the PDF says Rhesis.
"""

import io
import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from rhesis.backend.app import models
from rhesis.backend.app.services.organization_branding import read_favicon

logger = logging.getLogger(__name__)

# ReportLab draws rasters; an SVG favicon is left out.
_RASTER_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/x-icon",
    "image/vnd.microsoft.icon",
}


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
            logo=_logo_png(branding.favicon),
        )
    except Exception:
        logger.exception("report PDF branding failed for organization %s", organization.id)
        return DEFAULT_PDF_BRAND


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

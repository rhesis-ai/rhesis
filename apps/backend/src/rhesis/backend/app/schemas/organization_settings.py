"""Schemas for ``organization.organization_settings``.

Validation is strict on write: a malformed colour or an over-long product name
is rejected with a 422 so the settings form can show the operator what to fix.
That is the opposite of the env-var path in ``config/branding.ts``, which
silently falls back to the Rhesis default — nobody is standing in front of a
values file to read the error, but somebody is standing in front of this form.
"""

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: 6-digit hex only. Mirrors HEX_COLOR_PATTERN in the frontend's
#: ``config/branding.ts`` — the 3-digit form would widen what a deployment can
#: store, and MUI's colour manipulators need a parseable value.
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")

#: Letters, digits, spaces, hyphens. Rejects quotes, angle brackets and braces,
#: which would break out of the CSS/HTML boundaries the family name is
#: interpolated into. Mirrors SAFE_FONT_FAMILY_PATTERN on the frontend.
SAFE_FONT_FAMILY_PATTERN = re.compile(r"^[a-zA-Z0-9 -]+$")

MAX_PRODUCT_NAME_LENGTH = 60
MAX_FONT_FAMILY_LENGTH = 80

#: Font weights a brand font ships: light, regular, bold. The theme remaps
#: 500 -> 400 and 600/800 -> 700, so these three cover the whole UI.
FONT_WEIGHTS = ("300", "400", "700")

#: Below this the mark looks soft: the largest place it renders is the
#: onboarding header at 92 CSS px, which is 184 device px on a 2x display.
MIN_FAVICON_DIMENSION = 192

#: What we tell operators to upload. Comfortable for every render size, and
#: still only a few KB as a PNG.
RECOMMENDED_FAVICON_DIMENSION = 512


def _validate_hex_color(value: Optional[str], field_name: str) -> Optional[str]:
    """Normalize a brand colour to upper-case ``#RRGGBB``, or reject it."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if not HEX_COLOR_PATTERN.match(trimmed):
        raise ValueError(f"{field_name} must be a 6-digit hex colour in #RRGGBB form")
    return trimmed.upper()


def _validate_font_family(value: str) -> str:
    """Trim and bounds-check a CSS font-family name.

    The character class is narrow because this string is interpolated into a
    ``<style>`` block and a Google Fonts URL. Every Google family name fits it.
    """
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Font family cannot be empty")
    if len(trimmed) > MAX_FONT_FAMILY_LENGTH:
        raise ValueError(f"Font family must be at most {MAX_FONT_FAMILY_LENGTH} characters")
    if not SAFE_FONT_FAMILY_PATTERN.match(trimmed):
        raise ValueError("Font family may only contain letters, digits, spaces and hyphens")
    return trimmed


def _validate_product_name(value: Optional[str]) -> Optional[str]:
    """Trim a product name, or reject it when it would not fit a browser tab."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_PRODUCT_NAME_LENGTH:
        raise ValueError(f"product_name must be at most {MAX_PRODUCT_NAME_LENGTH} characters")
    return trimmed


class BrandingFavicon(BaseModel):
    """Descriptor for an uploaded favicon. Server-owned: written by the upload
    endpoint, never accepted from a settings PATCH body."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Object-storage path, relative to the storage root")
    content_type: str = Field(..., description="MIME type the asset is served with")
    filename: str = Field(..., description="Original filename, shown in the settings UI")
    sha256: str = Field(..., description="Content hash, used as the asset ETag")
    # Recorded at upload so the settings page can flag an icon that will look
    # blurry without re-downloading it. Null for SVG, which has no fixed
    # raster size.
    width: Optional[int] = Field(None, description="Pixel width, null for SVG")
    height: Optional[int] = Field(None, description="Pixel height, null for SVG")


class BrandingFont(BaseModel):
    """The organization's brand font, from either of two sources.

    ``google`` is pure configuration — a family name the browser loads from the
    Google Fonts stylesheet — so it is set through the settings PATCH.
    ``upload`` points at files in object storage and is written only by the
    font upload endpoint.
    """

    model_config = ConfigDict(extra="ignore")

    #: Defaulted for descriptors written before this field existed; every one
    #: of those was an upload, since Google was not an option then.
    source: Literal["google", "upload"] = Field(
        "upload", description="Where the font files come from"
    )
    family: str = Field(..., description="CSS font-family name, e.g. 'Inria Sans'")
    slug: Optional[str] = Field(
        None, description="Lowercased hyphenated family, used in filenames (upload only)"
    )
    weights: List[str] = Field(
        default_factory=list,
        description="Uploaded weights, a subset of 300/400/700, ascending (upload only)",
    )
    #: Weight -> stored file extension, so the asset endpoint can serve the
    #: right Content-Type without a second lookup.
    extensions: dict = Field(default_factory=dict, description="Weight -> file extension")
    sha256: dict = Field(default_factory=dict, description="Weight -> content hash")

    @field_validator("family")
    @classmethod
    def validate_family(cls, v: str) -> str:
        return _validate_font_family(v)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v: List[str]) -> List[str]:
        unknown = [w for w in v if w not in FONT_WEIGHTS]
        if unknown:
            raise ValueError(f"Unsupported font weights: {', '.join(unknown)}")
        return sorted(set(v))

    @model_validator(mode="after")
    def validate_upload_has_files(self) -> "BrandingFont":
        """An upload without a slug and weights would emit @font-face rules
        pointing at files that do not exist."""
        if self.source == "upload" and (not self.slug or not self.weights):
            raise ValueError("An uploaded font requires a slug and at least one weight")
        return self


class BrandingGoogleFont(BaseModel):
    """The writable font shape: a Google family and nothing else.

    Deliberately cannot express an upload — no slug, no weights, no paths — so
    a settings PATCH can never point the asset endpoint at storage it should
    not read.
    """

    model_config = ConfigDict(extra="forbid")

    source: Literal["google"] = Field(..., description="Must be 'google'")
    family: str = Field(..., description="Google Fonts family name, e.g. 'Roboto'")

    @field_validator("family")
    @classmethod
    def validate_family(cls, v: str) -> str:
        return _validate_font_family(v)


class BrandingSettings(BaseModel):
    """Per-organization white-label branding.

    Every field is optional, and each one falls back independently: an unset
    ``primary_color`` uses ``BRAND_PRIMARY_COLOR`` even when ``product_name``
    is set here. Setting a field to ``null`` clears it back to that fallback.

    Unknown keys are ignored rather than rejected: this is a response schema,
    and a stored key this version does not know about must not fail the read.
    Writes go through ``BrandingSettingsUpdate``, which does forbid them.
    """

    model_config = ConfigDict(extra="ignore")

    primary_color: Optional[str] = Field(
        None, description="Primary brand colour, 6-digit hex (e.g. '#6A1B9A')"
    )
    secondary_color: Optional[str] = Field(None, description="Secondary/CTA colour, 6-digit hex")
    product_name: Optional[str] = Field(
        None, description=f"Product name in page titles. Max {MAX_PRODUCT_NAME_LENGTH} characters"
    )
    favicon: Optional[BrandingFavicon] = Field(
        None, description="Uploaded favicon. Written by the upload endpoint"
    )
    font: Optional[BrandingFont] = Field(
        None, description="Uploaded brand font. Written by the upload endpoint"
    )

    @field_validator("primary_color")
    @classmethod
    def validate_primary_color(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hex_color(v, "primary_color")

    @field_validator("secondary_color")
    @classmethod
    def validate_secondary_color(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hex_color(v, "secondary_color")

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, v: Optional[str]) -> Optional[str]:
        return _validate_product_name(v)


class BrandingSettingsUpdate(BaseModel):
    """Writable subset of :class:`BrandingSettings`.

    ``favicon`` is absent on purpose: it points at object storage, so it is
    only ever written by its upload endpoint. Accepting it here would let a
    caller aim the asset endpoint at an arbitrary storage path.

    ``font`` is writable but only as a Google family — config, not bytes.
    Setting it to ``null`` clears whichever font is configured; uploading files
    still goes through the font endpoint, because multipart cannot ride in a
    JSON body.
    """

    model_config = ConfigDict(extra="forbid")

    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    product_name: Optional[str] = None
    font: Optional[BrandingGoogleFont] = None

    @field_validator("primary_color")
    @classmethod
    def validate_primary_color(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hex_color(v, "primary_color")

    @field_validator("secondary_color")
    @classmethod
    def validate_secondary_color(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hex_color(v, "secondary_color")

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, v: Optional[str]) -> Optional[str]:
        return _validate_product_name(v)


class OrganizationSettings(BaseModel):
    """Complete organization settings schema. Lenient on read, like
    :class:`BrandingSettings` — a future section is dropped from the response
    rather than breaking it."""

    model_config = ConfigDict(extra="ignore")

    version: int = Field(1, description="Settings schema version")
    branding: BrandingSettings = Field(default_factory=BrandingSettings)


class OrganizationSettingsUpdate(BaseModel):
    """Partial update. Only the sections present in the body are merged."""

    model_config = ConfigDict(extra="forbid")

    branding: Optional[BrandingSettingsUpdate] = None


class OrganizationSettingsRead(OrganizationSettings):
    """``GET /organizations/settings`` — settings plus the caller's affordances."""

    permitted_actions: List[str] = Field(
        default_factory=list,
        description="Capabilities the caller may exercise on these settings "
        "(e.g. organization:update).",
    )

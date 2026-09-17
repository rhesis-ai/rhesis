"""Per-organization branding assets: favicon and brand-font uploads.

Holds the validation, object-storage writes and descriptor bookkeeping behind
``/organizations/settings/branding/*`` so the router stays thin.

Assets live at ``branding/{org_id}/…`` and are read back through the asset
endpoint rather than a public URL: the storage bucket is private, and the
``file://`` backend used in local development has no presigned-URL support at
all, so proxying is the one path that behaves the same everywhere.
"""

import io
import json
import logging
import time
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException, UploadFile

from rhesis.backend.app.schemas.organization_settings import (
    FONT_WEIGHTS,
    MAX_FONT_FAMILY_LENGTH,
    SAFE_FONT_FAMILY_PATTERN,
    BrandingFavicon,
    BrandingFont,
)
from rhesis.backend.app.services.storage_service import StorageService
from rhesis.backend.app.utils.uploads import read_upload_capped, store_bytes_async

logger = logging.getLogger(__name__)

#: A favicon is a handful of KB. The cap is generous enough for a retina PNG
#: and small enough that the asset endpoint never streams anything large.
MAX_FAVICON_BYTES = 512 * 1024

#: A full-weight TTF is typically 100-300 KB; woff2 far less.
MAX_FONT_BYTES = 2 * 1024 * 1024

#: Extension per accepted favicon type. SVG is allowed but served under a
#: locked-down CSP (see ``asset_response_headers``) — a same-origin SVG can
#: carry script, and the favicon is fetched from our own origin.
FAVICON_CONTENT_TYPES = {
    "image/png": ".png",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
}

#: Google answers 400 for a family it does not publish, which is exactly the
#: "is this openly available" question the settings form needs answered.
GOOGLE_FONTS_CSS_URL = "https://fonts.googleapis.com/css2"

GOOGLE_FONT_CHECK_TIMEOUT_S = 5.0

#: The catalogue behind the family picker. This is the endpoint fonts.google.com
#: itself calls, so it needs no API key — unlike the Web Fonts Developer API,
#: which would add a credential to configure and to rotate for a list of public
#: names. It is not a documented contract, so every failure here degrades to an
#: empty list: the field stays free text and ``verify_google_font`` remains the
#: check that actually matters.
GOOGLE_FONTS_METADATA_URL = "https://fonts.google.com/metadata/fonts"

GOOGLE_FONTS_CATALOG_TIMEOUT_S = 10.0

#: Google publishes a handful of new families a month, so a day-old list is
#: never meaningfully wrong.
GOOGLE_FONTS_CATALOG_TTL_S = 24 * 60 * 60

#: A failed fetch is retried far sooner: caching "no suggestions" for a whole
#: day would turn one transient blip on a cold pod into a day without a picker.
GOOGLE_FONTS_CATALOG_ERROR_TTL_S = 5 * 60

#: Process-local rather than Redis: one request per pod per day is not worth a
#: database allocation or a cache invalidation story, and a cold pod serving a
#: stale-by-seconds list has no consequence.
_catalog_cache: dict = {"families": None, "fetched_at": 0.0}

FONT_CONTENT_TYPES = {
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def slugify_font(family: str) -> str:
    """ "Inria Sans" -> "inria-sans". Mirrors slugifyFont in config/branding.ts."""
    slug = "".join(c if c.isalnum() else "-" for c in family.lower())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def favicon_filename(content_type: str) -> str:
    """Storage filename for a favicon of the given type."""
    return f"favicon{FAVICON_CONTENT_TYPES[content_type]}"


def font_filename(slug: str, weight: str, extension: str) -> str:
    """Storage filename for one weight of a brand font."""
    return f"fonts/{slug}-{weight}{extension}"


def asset_response_headers(content_type: str, sha256: str) -> dict:
    """Headers for serving a branding asset back to a browser.

    ``nosniff`` stops a mislabelled upload being re-interpreted as HTML, and
    the CSP neuters scripts and external references inside an SVG favicon — it
    is served from our own origin, so without this an org admin could upload a
    same-origin script.
    """
    return {
        "Content-Type": content_type,
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        "ETag": f'"{sha256}"',
        # A floor, not the browser's answer: the frontend proxy sets its own
        # Cache-Control, keyed on whether the URL carries a content hash. This
        # one only matters to a direct API caller.
        "Cache-Control": "private, max-age=60, must-revalidate",
    }


def _storage() -> StorageService:
    return StorageService()


def _raster_dimensions(content: bytes) -> tuple:
    """Return ``(width, height)`` for raster bytes, rejecting anything Pillow
    cannot open.

    This is the real content check: ``content_type`` is whatever the client
    said, so a text/html payload labelled ``image/png`` would otherwise be
    stored and later served from our own origin.
    """
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:  # pragma: no cover - Pillow is a hard dependency
        logger.warning("Pillow unavailable; skipping favicon content validation")
        return None, None

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        # verify() consumes the file object, so reopen to read the size.
        with Image.open(io.BytesIO(content)) as image:
            return image.width, image.height
    # DecompressionBombError derives straight from Exception, not OSError, so
    # it has to be named: a small PNG declaring gigapixel dimensions would
    # otherwise escape as a 500 instead of a rejected upload.
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
    ) as e:
        raise HTTPException(
            status_code=422,
            detail="Favicon is not a readable image file.",
        ) from e


def _validate_svg(content: bytes) -> None:
    """Reject anything that is not actually an SVG document.

    Pillow cannot read SVG, so this is the equivalent content check. It is not
    a sanitiser — a valid SVG may still contain script, which is why the asset
    endpoint serves it under a sandbox CSP.
    """
    text = content.decode("utf-8", errors="ignore")

    # ElementTree expands internal entities, so a 512 KB file within the size
    # cap can still blow up the worker's memory (the "billion laughs" attack).
    # A favicon has no reason to declare a doctype or entities, so refuse both
    # rather than parse them.
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise HTTPException(
            status_code=422,
            detail="Favicon SVG must not declare a doctype or entities.",
        )

    try:
        root = ElementTree.fromstring(text)
    except (ElementTree.ParseError, UnicodeDecodeError, ValueError) as e:
        raise HTTPException(status_code=422, detail="Favicon is not a valid SVG document.") from e

    # ElementTree reports the tag as '{http://www.w3.org/2000/svg}svg'.
    if not root.tag.rsplit("}", 1)[-1].lower() == "svg":
        raise HTTPException(status_code=422, detail="Favicon is not a valid SVG document.")


async def upload_favicon(organization_id: str, upload: UploadFile) -> BrandingFavicon:
    """Store a favicon for the organization and return its descriptor."""
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type not in FAVICON_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Favicon type '{content_type or 'unknown'}' is not allowed. "
                f"Allowed types: {', '.join(sorted(FAVICON_CONTENT_TYPES))}."
            ),
        )

    content = await read_upload_capped(upload, MAX_FAVICON_BYTES, "Favicon")

    # Dimensions are recorded so the settings page can warn about an icon that
    # will render soft, without having to fetch and measure it again.
    if content_type == "image/svg+xml":
        _validate_svg(content)
        width = height = None
    else:
        width, height = _raster_dimensions(content)

    storage = _storage()
    dest_path = storage.get_branding_path(organization_id, favicon_filename(content_type))
    stored_path, sha256 = await store_bytes_async(storage, content, dest_path, content_type)

    return BrandingFavicon(
        path=stored_path,
        content_type=content_type,
        filename=upload.filename or favicon_filename(content_type),
        sha256=sha256,
        width=width,
        height=height,
    )


async def delete_favicon(favicon: Optional[dict]) -> None:
    """Remove a stored favicon. Missing files are not an error — the descriptor
    is being cleared either way, and a failed delete must not block that."""
    if not favicon or not favicon.get("path"):
        return
    try:
        await _storage().delete_object(favicon["path"])
    except Exception as e:  # noqa: BLE001 — best-effort cleanup
        logger.warning(f"Could not delete branding favicon {favicon['path']}: {e}")


def _parse_font_catalog(body: str) -> list:
    """Family names from the metadata payload, filtered to what we would accept.

    Suggesting a name our own validator rejects would be a trap, so the same
    character rule is applied here.
    """
    # Some Google endpoints prefix JSON with an XSSI guard line.
    if body.startswith(")]}'"):
        body = body.split("\n", 1)[-1]

    payload = json.loads(body)
    families = [
        entry.get("family", "")
        for entry in payload.get("familyMetadataList", [])
        if isinstance(entry, dict)
    ]
    return sorted(
        {
            family
            for family in families
            if family
            and len(family) <= MAX_FONT_FAMILY_LENGTH
            and SAFE_FONT_FAMILY_PATTERN.match(family)
        }
    )


def list_google_fonts() -> list:
    """Every family Google publishes, for the settings page's picker.

    Returns an empty list when the catalogue cannot be fetched — an air-gapped
    deployment, a blocked egress route, or a change to this undocumented
    payload. The picker then accepts free text, which is what it does anyway;
    only the suggestions are lost.

    Synchronous on purpose: the route that calls it is a ``def`` handler, so
    this runs in the anyio threadpool where a blocking request is fine.
    """
    now = time.monotonic()
    cached = _catalog_cache["families"]
    ttl = GOOGLE_FONTS_CATALOG_TTL_S if cached else GOOGLE_FONTS_CATALOG_ERROR_TTL_S
    if cached is not None and now - _catalog_cache["fetched_at"] < ttl:
        return cached

    try:
        response = httpx.get(GOOGLE_FONTS_METADATA_URL, timeout=GOOGLE_FONTS_CATALOG_TIMEOUT_S)
        response.raise_for_status()
        families = _parse_font_catalog(response.text)
    except (httpx.HTTPError, json.JSONDecodeError, ValueError, KeyError) as e:
        logger.info(f"Could not fetch the Google Fonts catalogue ({e}); serving no suggestions")
        # Cache the failure too, so a blocked deployment does not retry on
        # every page load — but keep any list we managed to fetch earlier.
        families = cached if cached is not None else []

    _catalog_cache["families"] = families
    _catalog_cache["fetched_at"] = now
    return families


async def verify_google_font(family: str) -> None:
    """Confirm Google publishes ``family``, rejecting a typo before it is stored.

    Google's stylesheet endpoint answers 400 for an unknown family, so one
    request settles it. A network failure is *not* treated as a rejection: an
    air-gapped or egress-restricted deployment cannot reach Google, and
    refusing the save there would make the field unusable rather than safe. The
    cost of accepting an unverifiable name is that the browser falls back to
    the default typeface.
    """
    url = f"{GOOGLE_FONTS_CSS_URL}?family={quote(family)}"
    try:
        async with httpx.AsyncClient(timeout=GOOGLE_FONT_CHECK_TIMEOUT_S) as client:
            response = await client.get(url)
    except httpx.HTTPError as e:
        logger.info(f"Could not verify Google font '{family}' ({e}); accepting unverified")
        return

    if response.status_code == 400:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{family}' is not available on Google Fonts. "
                "Check the spelling at fonts.google.com."
            ),
        )

    if response.status_code >= 500:
        logger.info(
            f"Google Fonts returned {response.status_code} verifying '{family}'; "
            "accepting unverified"
        )


async def upload_font(
    organization_id: str,
    family: str,
    files_by_weight: dict,
) -> BrandingFont:
    """Store one or more weights of a brand font and return its descriptor.

    ``files_by_weight`` maps a weight in ``FONT_WEIGHTS`` to an ``UploadFile``.
    Weights that are absent are simply not uploaded; the browser synthesises
    them from the nearest available weight.
    """
    family = family.strip()
    if not family or not SAFE_FONT_FAMILY_PATTERN.match(family):
        raise HTTPException(
            status_code=422,
            detail="Font family may only contain letters, digits, spaces and hyphens.",
        )

    provided = {w: f for w, f in files_by_weight.items() if f is not None}
    if not provided:
        raise HTTPException(status_code=422, detail="At least one font weight is required.")

    unknown = sorted(set(provided) - set(FONT_WEIGHTS))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported font weights: {', '.join(unknown)}.",
        )

    slug = slugify_font(family)
    storage = _storage()
    extensions: dict = {}
    hashes: dict = {}

    for weight in sorted(provided):
        upload = provided[weight]
        extension = Path(upload.filename or "").suffix.lower()
        if extension not in FONT_CONTENT_TYPES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Font file for weight {weight} must be one of "
                    f"{', '.join(sorted(FONT_CONTENT_TYPES))}."
                ),
            )

        content = await read_upload_capped(upload, MAX_FONT_BYTES, f"Font file for weight {weight}")
        dest_path = storage.get_branding_path(
            organization_id, font_filename(slug, weight, extension)
        )
        _, sha256 = await store_bytes_async(
            storage, content, dest_path, FONT_CONTENT_TYPES[extension]
        )
        extensions[weight] = extension
        hashes[weight] = sha256

    return BrandingFont(
        source="upload",
        family=family,
        slug=slug,
        weights=sorted(extensions),
        extensions=extensions,
        sha256=hashes,
    )


async def delete_font(
    organization_id: str,
    font: Optional[dict],
    keep_weights: Optional[set] = None,
) -> None:
    """Remove stored weights of a brand font. Best-effort, like the favicon.

    ``keep_weights`` spares the weights a replacement upload just wrote, so a
    re-upload under the same family cleans up the weights it dropped without
    deleting the ones it kept.
    """
    if not font or not font.get("slug"):
        return
    storage = _storage()
    for weight, extension in (font.get("extensions") or {}).items():
        if keep_weights and weight in keep_weights:
            continue
        path = storage.get_branding_path(
            organization_id, font_filename(font["slug"], weight, extension)
        )
        try:
            await storage.delete_object(path)
        except Exception as e:  # noqa: BLE001 — best-effort cleanup
            logger.warning(f"Could not delete branding font {path}: {e}")


def read_favicon(favicon: Optional[dict]) -> tuple:
    """Return ``(bytes, content_type, sha256)`` for the stored favicon."""
    if not favicon or not favicon.get("path"):
        raise HTTPException(status_code=404, detail="No favicon configured.")
    content = _storage().get_object_bytes(favicon["path"])
    if content is None:
        raise HTTPException(status_code=404, detail="Favicon file is missing from storage.")
    return (
        content,
        favicon.get("content_type", "application/octet-stream"),
        favicon.get("sha256", ""),
    )


def read_font_weight(
    organization_id: str,
    font: Optional[dict],
    weight: str,
    expected_slug: Optional[str] = None,
) -> tuple:
    """Return ``(bytes, content_type, sha256)`` for one weight of the brand font.

    ``expected_slug`` is the slug the caller's ``@font-face`` rule asked for.
    When it no longer matches the configured font the request is stale — the
    org renamed its family — and 404 is the honest answer; serving the current
    font under the old name would cache the wrong bytes against that filename.
    """
    if not font or not font.get("slug"):
        raise HTTPException(status_code=404, detail="No brand font configured.")

    if expected_slug and expected_slug != font["slug"]:
        raise HTTPException(status_code=404, detail="Font file not found.")

    extension = (font.get("extensions") or {}).get(weight)
    if not extension:
        raise HTTPException(status_code=404, detail=f"Weight {weight} is not configured.")

    path = _storage().get_branding_path(
        organization_id, font_filename(font["slug"], weight, extension)
    )
    content = _storage().get_object_bytes(path)
    if content is None:
        raise HTTPException(status_code=404, detail="Font file is missing from storage.")

    return (
        content,
        FONT_CONTENT_TYPES.get(extension, "application/octet-stream"),
        (font.get("sha256") or {}).get(weight, ""),
    )

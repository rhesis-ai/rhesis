"""
🎨 Branding service unit tests

Focused on ``verify_google_font``, whose whole job is deciding when *not* to
reject: Google's 400 is authoritative, everything else is a reason to accept an
unverified family rather than make the field unusable offline.

Run with: python -m pytest tests/backend/services/test_organization_branding.py -v
"""

import io
import json
from pathlib import PurePosixPath, PureWindowsPath
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from rhesis.backend.app.services import organization_branding
from rhesis.backend.app.services.organization_branding import (
    _parse_font_catalog,
    _raster_dimensions,
    favicon_filename,
    font_filename,
    list_google_fonts,
    slugify_font,
    verify_google_font,
)
from rhesis.backend.app.services.storage_service import StorageService


def _client_returning(response=None, error=None):
    """Patch the httpx client the verifier builds, returning ``response`` or raising."""
    client = AsyncMock()
    if error is not None:
        client.get.side_effect = error
    else:
        client.get.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = client
    return patch("httpx.AsyncClient", return_value=context)


class TestVerifyGoogleFont:
    async def test_accepts_a_published_family(self):
        """✅ A 200 from the stylesheet endpoint means Google publishes it."""
        with _client_returning(httpx.Response(200)):
            await verify_google_font("Roboto")

    async def test_rejects_an_unknown_family(self):
        """✅ Google answers 400 for a family it does not have — a typo, caught on save."""
        with _client_returning(httpx.Response(400)):
            with pytest.raises(HTTPException) as excinfo:
                await verify_google_font("Robото Fake")

        assert excinfo.value.status_code == 422
        assert "fonts.google.com" in excinfo.value.detail

    async def test_accepts_when_google_is_unreachable(self):
        """✅ An air-gapped deployment must still be able to save the field.

        Treating a network failure as rejection would make the option unusable
        wherever egress is restricted, which is worse than accepting a name we
        could not check — the cost of a wrong one is a fallback typeface.
        """
        with _client_returning(error=httpx.ConnectError("no route to host")):
            await verify_google_font("Roboto")

    async def test_accepts_when_google_returns_a_server_error(self):
        """✅ A 5xx is Google's problem, not evidence the family is wrong."""
        with _client_returning(httpx.Response(503)):
            await verify_google_font("Roboto")

    async def test_sends_the_family_url_encoded(self):
        """✅ A two-word family must not break the query string."""
        client = AsyncMock()
        client.get.return_value = httpx.Response(200)
        context = AsyncMock()
        context.__aenter__.return_value = client

        with patch("httpx.AsyncClient", return_value=context):
            await verify_google_font("Open Sans")

        assert "Open%20Sans" in client.get.call_args.args[0]


class TestSlugifyFont:
    @pytest.mark.parametrize(
        ("family", "expected"),
        [
            ("Inria Sans", "inria-sans"),
            ("IBM Plex Sans", "ibm-plex-sans"),
            ("Roboto", "roboto"),
            ("Press Start 2P", "press-start-2p"),
        ],
    )
    def test_matches_the_frontend_slug(self, family, expected):
        """✅ Must agree with slugifyFont in config/branding.ts.

        The slug is the filename the page's @font-face rule requests, so a
        disagreement means the browser asks for a file that is not there.
        """
        assert slugify_font(family) == expected


def _catalog_response(text: str, status_code: int = 200) -> httpx.Response:
    """`raise_for_status` needs a request attached, which a bare Response lacks."""
    return httpx.Response(
        status_code,
        text=text,
        request=httpx.Request("GET", "https://fonts.google.com/metadata/fonts"),
    )


CATALOG_BODY = json.dumps(
    {
        "familyMetadataList": [
            {"family": "Roboto"},
            {"family": "Open Sans"},
            {"family": "ABeeZee"},
        ]
    }
)


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    """The catalogue cache is process-local, so it leaks between tests."""
    organization_branding._catalog_cache = {"families": None, "fetched_at": 0.0}
    yield
    organization_branding._catalog_cache = {"families": None, "fetched_at": 0.0}


class TestFontCatalog:
    def test_parses_family_names(self):
        """✅ Only the names are needed; the rest of the payload is ignored."""
        assert _parse_font_catalog(CATALOG_BODY) == ["ABeeZee", "Open Sans", "Roboto"]

    def test_strips_an_xssi_guard(self):
        """✅ Some Google endpoints prefix JSON with `)]}'`."""
        assert _parse_font_catalog(")]}'\n" + CATALOG_BODY) == [
            "ABeeZee",
            "Open Sans",
            "Roboto",
        ]

    def test_drops_families_our_validator_would_reject(self):
        """✅ Suggesting a name that fails validation on save would be a trap."""
        body = json.dumps(
            {"familyMetadataList": [{"family": "Roboto"}, {"family": "Noto Sans (Display)"}]}
        )

        assert _parse_font_catalog(body) == ["Roboto"]

    def test_fetches_and_caches_the_catalogue(self):
        """✅ One request per pod per day, not one per page load."""
        with patch("httpx.get", return_value=_catalog_response(CATALOG_BODY)) as get:
            first = list_google_fonts()
            second = list_google_fonts()

        assert first == second == ["ABeeZee", "Open Sans", "Roboto"]
        get.assert_called_once()

    def test_returns_an_empty_list_when_google_is_unreachable(self):
        """✅ An air-gapped deployment loses the suggestions, not the field."""
        with patch("httpx.get", side_effect=httpx.ConnectError("no route")):
            assert list_google_fonts() == []

    def test_returns_an_empty_list_on_an_unexpected_payload(self):
        """✅ This endpoint is undocumented, so a shape change must not 500."""
        with patch("httpx.get", return_value=_catalog_response("not json")):
            assert list_google_fonts() == []

    def test_keeps_a_previously_fetched_list_when_a_refresh_fails(self):
        """✅ A transient outage should not blank a catalogue we already have."""
        with patch("httpx.get", return_value=_catalog_response(CATALOG_BODY)):
            list_google_fonts()

        organization_branding._catalog_cache["fetched_at"] = 0.0
        with patch("httpx.get", side_effect=httpx.ConnectError("no route")):
            assert list_google_fonts() == ["ABeeZee", "Open Sans", "Roboto"]


class TestRasterDimensions:
    def test_reads_the_size_of_a_real_png(self):
        """✅ The dimensions the settings page warns on come from here."""
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGBA", (64, 32)).save(buffer, format="PNG")

        assert _raster_dimensions(buffer.getvalue()) == (64, 32)

    def test_rejects_bytes_that_are_not_an_image(self):
        """✅ `content_type` is client-supplied, so the bytes are what decide."""
        with pytest.raises(HTTPException) as excinfo:
            _raster_dimensions(b"<html><script>alert(1)</script></html>")

        assert excinfo.value.status_code == 422

    def test_rejects_a_decompression_bomb_as_a_422(self):
        """✅ DecompressionBombError derives from Exception, not OSError.

        Left out of the except clause it escapes as a 500, so a small PNG
        declaring gigapixel dimensions would crash the request instead of
        being refused.
        """
        from PIL import Image

        with patch("PIL.Image.open", side_effect=Image.DecompressionBombError("too big")):
            with pytest.raises(HTTPException) as excinfo:
                _raster_dimensions(b"whatever")

        assert excinfo.value.status_code == 422


class TestStoredPaths:
    """What lands in the descriptor, and what a hostile upload cannot do to it."""

    def test_stored_paths_are_backend_and_platform_neutral(self):
        """✅ The descriptor holds a relative, forward-slash path.

        It is persisted in the database and read back by whatever is serving —
        possibly a different OS, and certainly a different storage backend than
        the one that wrote it. `StorageService._full_path` is what turns it into
        a GCS key or a local path at read time.
        """
        path = StorageService.get_branding_path(
            "org-1", font_filename("inria-sans", "400", ".woff2")
        )

        assert path == "branding/org-1/fonts/inria-sans-400.woff2"
        assert "\\" not in path
        assert not PurePosixPath(path).is_absolute()

    def test_stored_path_joins_correctly_on_either_platform(self):
        """✅ The same stored value resolves under a Windows or POSIX root."""
        path = StorageService.get_branding_path("org-1", "favicon.png")

        assert PureWindowsPath(r"C:\Temp\rhesis-files") / path == PureWindowsPath(
            r"C:\Temp\rhesis-files\branding\org-1\favicon.png"
        )
        assert PurePosixPath("/tmp/rhesis-files") / path == PurePosixPath(
            "/tmp/rhesis-files/branding/org-1/favicon.png"
        )

    def test_favicon_filename_ignores_the_uploaded_name(self):
        """✅ The stored name comes from the content type, never the upload.

        A filename is attacker-controlled, so letting it reach the path would
        be the classic traversal bug.
        """
        assert favicon_filename("image/png") == "favicon.png"
        assert favicon_filename("image/svg+xml") == "favicon.svg"

    def test_a_hostile_family_cannot_escape_the_org_prefix(self):
        """✅ The slug is the only caller-derived part of a font path."""
        path = StorageService.get_branding_path(
            "org-1", font_filename(slugify_font("../../etc/passwd"), "400", ".ttf")
        )

        assert path == "branding/org-1/fonts/etc-passwd-400.ttf"
        assert ".." not in path

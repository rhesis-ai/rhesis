"""
🎨 Organization Settings Routes Testing Suite

Covers the org-level settings blob and the branding section stored in it.

Endpoints tested:
- GET    /organizations/settings
- PATCH  /organizations/settings           (deep merge, explicit null clears)
- POST   /organizations/settings/branding/favicon
- DELETE /organizations/settings/branding/favicon
- POST   /organizations/settings/branding/font
- DELETE /organizations/settings/branding/font
- GET    /organizations/settings/branding/assets/{asset}

Run with: python -m pytest tests/backend/routes/test_organization_settings.py -v
"""

import io
from unittest.mock import patch

import pytest
from fastapi import status

SETTINGS_ENDPOINT = "/organizations/settings"
FAVICON_ENDPOINT = f"{SETTINGS_ENDPOINT}/branding/favicon"
FONT_ENDPOINT = f"{SETTINGS_ENDPOINT}/branding/font"
ASSETS_ENDPOINT = f"{SETTINGS_ENDPOINT}/branding/assets"


def _png(size: int = 256) -> bytes:
    """A real square PNG. Built rather than inlined because the upload endpoint
    now opens the bytes with Pillow and records the dimensions."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGBA", (size, size), (0, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"></svg>'

#: Patch target for the outbound Google Fonts availability check.
VERIFY_GOOGLE_FONT = "rhesis.backend.app.services.organization_branding.verify_google_font"


class TestOrganizationSettingsRead:
    """GET /organizations/settings"""

    def test_returns_default_structure(self, authenticated_client):
        """✅ A brand-new org reports the default settings blob, not null."""
        response = authenticated_client.get(SETTINGS_ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["version"] == 1
        assert "branding" in data

    def test_includes_permitted_actions(self, authenticated_client):
        """✅ Affordances are broadcast so the UI can gate its edit controls."""
        response = authenticated_client.get(SETTINGS_ENDPOINT)

        assert "permitted_actions" in response.json()

    def test_requires_authentication(self, client):
        """🔐 An anonymous caller gets no org settings."""
        response = client.get(SETTINGS_ENDPOINT)

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_settings_path_is_not_parsed_as_an_org_id(self, authenticated_client):
        """✅ `/settings` must not be captured by `/{organization_id}`.

        Route order is load-bearing here: declared the other way round, FastAPI
        would try to parse "settings" as a UUID and answer 422.
        """
        response = authenticated_client.get(SETTINGS_ENDPOINT)

        assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY


class TestOrganizationSettingsUpdate:
    """PATCH /organizations/settings"""

    def test_updates_branding_colors(self, authenticated_client):
        """✅ Colours round-trip, normalised to upper case."""
        response = authenticated_client.patch(
            SETTINGS_ENDPOINT,
            json={"branding": {"primary_color": "#6a1b9a"}},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["branding"]["primary_color"] == "#6A1B9A"

    def test_deep_merges_rather_than_replacing(self, authenticated_client):
        """✅ A second PATCH leaves untouched fields alone."""
        authenticated_client.patch(
            SETTINGS_ENDPOINT,
            json={"branding": {"primary_color": "#112233", "product_name": "Acme"}},
        )
        response = authenticated_client.patch(
            SETTINGS_ENDPOINT, json={"branding": {"product_name": "Acme Corp"}}
        )

        branding = response.json()["branding"]
        assert branding["product_name"] == "Acme Corp"
        assert branding["primary_color"] == "#112233"

    def test_explicit_null_clears_a_field(self, authenticated_client):
        """✅ Clearing is what reverts a field to the env-var default."""
        authenticated_client.patch(
            SETTINGS_ENDPOINT, json={"branding": {"primary_color": "#112233"}}
        )
        response = authenticated_client.patch(
            SETTINGS_ENDPOINT, json={"branding": {"primary_color": None}}
        )

        assert response.json()["branding"]["primary_color"] is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"branding": {"primary_color": "#fff"}},
            {"branding": {"primary_color": "6A1B9A"}},
            {"branding": {"secondary_color": "rebeccapurple"}},
            {"branding": {"product_name": "x" * 61}},
        ],
    )
    def test_rejects_malformed_values(self, authenticated_client, payload):
        """✅ Bad input is rejected, not silently defaulted.

        The env-var path falls back quietly because nobody is watching a values
        file; here somebody is looking at a form and needs the error.
        """
        response = authenticated_client.patch(SETTINGS_ENDPOINT, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_a_null_branding_section_is_a_no_op(self, authenticated_client):
        """✅ `{"branding": null}` must not 500.

        A section is not a value — each field inside clears on its own. Merging
        the null in left the stored blob with `branding: null`, which the
        non-optional response model then rejected during serialization.
        """
        authenticated_client.patch(SETTINGS_ENDPOINT, json={"branding": {"product_name": "Acme"}})
        response = authenticated_client.patch(SETTINGS_ENDPOINT, json={"branding": None})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["branding"]["product_name"] == "Acme"

    def test_rejects_favicon_in_the_patch_body(self, authenticated_client):
        """✅ Storage-backed descriptors are writable only by their upload endpoint.

        Accepting one here would let a caller point the asset endpoint at an
        arbitrary storage path.
        """
        response = authenticated_client.patch(
            SETTINGS_ENDPOINT,
            json={"branding": {"favicon": {"path": "branding/other-org/favicon.png"}}},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_requires_authentication(self, client):
        """🔐 An anonymous caller cannot rebrand an organization."""
        response = client.patch(SETTINGS_ENDPOINT, json={"branding": {"product_name": "Acme"}})

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


class TestBrandingFavicon:
    """POST/DELETE /organizations/settings/branding/favicon"""

    def test_upload_records_a_descriptor(self, authenticated_client):
        """✅ A successful upload writes path, type, filename and hash."""
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.png", io.BytesIO(_png()), "image/png")},
        )

        assert response.status_code == status.HTTP_200_OK
        favicon = response.json()["branding"]["favicon"]
        assert favicon["content_type"] == "image/png"
        assert favicon["filename"] == "icon.png"
        assert favicon["path"].endswith("favicon.png")
        assert favicon["sha256"]

    def test_records_the_dimensions(self, authenticated_client):
        """✅ Measured at upload so the settings page can flag a soft icon later."""
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.png", io.BytesIO(_png(256)), "image/png")},
        )

        favicon = response.json()["branding"]["favicon"]
        assert (favicon["width"], favicon["height"]) == (256, 256)

    def test_leaves_svg_dimensions_unset(self, authenticated_client):
        """✅ An SVG has no fixed raster size, so there is nothing to warn about."""
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.svg", io.BytesIO(SVG_BYTES), "image/svg+xml")},
        )

        favicon = response.json()["branding"]["favicon"]
        assert favicon["width"] is None
        assert favicon["height"] is None

    def test_rejects_a_disallowed_type(self, authenticated_client):
        """✅ The favicon is served from our own origin, so the type allowlist matters."""
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("payload.html", io.BytesIO(b"<script>"), "text/html")},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rejects_a_non_image_wearing_an_image_content_type(self, authenticated_client):
        """✅ `content_type` is whatever the client said, so the bytes are checked too.

        Without this, HTML labelled `image/png` would be stored and later
        served back from our own origin.
        """
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("payload.png", io.BytesIO(b"<html><script>"), "image/png")},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rejects_an_svg_declaring_entities(self, authenticated_client):
        """✅ ElementTree expands internal entities, so a 512 KB file can still
        exhaust the worker's memory. A favicon never needs a doctype."""
        bomb = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE lolz [<!ENTITY lol "lol">]>'
            b'<svg xmlns="http://www.w3.org/2000/svg">&lol;</svg>'
        )
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("bomb.svg", io.BytesIO(bomb), "image/svg+xml")},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_answers_304_when_the_etag_matches(self, authenticated_client):
        """✅ The unversioned URL is revalidated, so a match must not re-send the body."""
        authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.png", io.BytesIO(_png()), "image/png")},
        )
        first = authenticated_client.get(f"{ASSETS_ENDPOINT}/favicon")

        second = authenticated_client.get(
            f"{ASSETS_ENDPOINT}/favicon",
            headers={"If-None-Match": first.headers["etag"]},
        )

        assert second.status_code == status.HTTP_304_NOT_MODIFIED
        assert not second.content

    def test_rejects_a_non_svg_wearing_an_svg_content_type(self, authenticated_client):
        """✅ Pillow cannot read SVG, so it gets its own content check."""
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("payload.svg", io.BytesIO(b"<html>nope</html>"), "image/svg+xml")},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rejects_an_oversized_file(self, authenticated_client):
        """✅ Over the 512 KB cap is refused rather than stored."""
        oversized = io.BytesIO(b"\x00" * (512 * 1024 + 1))
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("big.png", oversized, "image/png")},
        )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    def test_replacing_with_another_format_leaves_no_stale_dimensions(self, authenticated_client):
        """✅ The descriptor is replaced, not merged, so a PNG's size does not
        linger on the SVG that replaced it."""
        authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.png", io.BytesIO(_png(256)), "image/png")},
        )
        response = authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.svg", io.BytesIO(SVG_BYTES), "image/svg+xml")},
        )

        favicon = response.json()["branding"]["favicon"]
        assert favicon["width"] is None
        assert favicon["height"] is None

    def test_delete_clears_the_descriptor(self, authenticated_client):
        """✅ Removing the favicon reverts to the deployment default."""
        authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.png", io.BytesIO(_png()), "image/png")},
        )
        response = authenticated_client.delete(FAVICON_ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["branding"]["favicon"] is None


class TestGoogleBrandFont:
    """A Google family is config, so it is set through PATCH /settings."""

    def test_sets_a_google_family(self, authenticated_client):
        """✅ No files involved — the browser loads it from the Google stylesheet."""
        with patch(VERIFY_GOOGLE_FONT, return_value=None):
            response = authenticated_client.patch(
                SETTINGS_ENDPOINT,
                json={"branding": {"font": {"source": "google", "family": "Roboto"}}},
            )

        assert response.status_code == status.HTTP_200_OK
        font = response.json()["branding"]["font"]
        assert font["source"] == "google"
        assert font["family"] == "Roboto"
        assert font["weights"] == []

    def test_verifies_the_family_against_google(self, authenticated_client):
        """✅ A typo is caught on save rather than silently falling back."""
        with patch(VERIFY_GOOGLE_FONT) as verify:
            authenticated_client.patch(
                SETTINGS_ENDPOINT,
                json={"branding": {"font": {"source": "google", "family": "Roboto"}}},
            )

        verify.assert_awaited_once_with("Roboto")

    def test_rejects_an_unsafe_family(self, authenticated_client):
        """✅ Same character rule as an upload: it lands in a <style> block."""
        response = authenticated_client.patch(
            SETTINGS_ENDPOINT,
            json={
                "branding": {"font": {"source": "google", "family": "</style><script>x</script>"}}
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rejects_an_upload_shaped_font_in_the_patch_body(self, authenticated_client):
        """✅ PATCH cannot express an upload, so it cannot aim at storage.

        A slug and weights here would let a caller point the asset endpoint at
        files they did not upload.
        """
        response = authenticated_client.patch(
            SETTINGS_ENDPOINT,
            json={
                "branding": {
                    "font": {
                        "source": "upload",
                        "family": "Inria Sans",
                        "slug": "inria-sans",
                        "weights": ["400"],
                    }
                }
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_clearing_the_font_via_patch(self, authenticated_client):
        """✅ Null reverts to BRAND_FONT_* and then the built-in typeface."""
        with patch(VERIFY_GOOGLE_FONT, return_value=None):
            authenticated_client.patch(
                SETTINGS_ENDPOINT,
                json={"branding": {"font": {"source": "google", "family": "Roboto"}}},
            )
        response = authenticated_client.patch(SETTINGS_ENDPOINT, json={"branding": {"font": None}})

        assert response.json()["branding"]["font"] is None

    def test_switching_from_upload_to_google_replaces_the_descriptor(self, authenticated_client):
        """✅ The upload's slug and weights must not survive the switch."""
        authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("f.ttf", io.BytesIO(b"ttf"), "font/ttf")},
        )
        with patch(VERIFY_GOOGLE_FONT, return_value=None):
            response = authenticated_client.patch(
                SETTINGS_ENDPOINT,
                json={"branding": {"font": {"source": "google", "family": "Roboto"}}},
            )

        font = response.json()["branding"]["font"]
        assert font["source"] == "google"
        assert font["slug"] is None
        assert font["weights"] == []

    def test_switching_to_google_stops_serving_the_uploaded_files(self, authenticated_client):
        """✅ The stranded upload is deleted, not left readable in storage."""
        authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("f.ttf", io.BytesIO(b"ttf"), "font/ttf")},
        )
        with patch(VERIFY_GOOGLE_FONT, return_value=None):
            authenticated_client.patch(
                SETTINGS_ENDPOINT,
                json={"branding": {"font": {"source": "google", "family": "Roboto"}}},
            )

        response = authenticated_client.get(
            f"{ASSETS_ENDPOINT}/font-400", params={"slug": "inria-sans"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBrandingFont:
    """POST/DELETE /organizations/settings/branding/font"""

    def test_upload_records_weights_and_slug(self, authenticated_client):
        """✅ Only the uploaded weights are recorded, with a slug derived from the family."""
        response = authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={
                "weight_400": ("inria-400.ttf", io.BytesIO(b"ttf-bytes"), "font/ttf"),
                "weight_700": ("inria-700.ttf", io.BytesIO(b"ttf-bytes"), "font/ttf"),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        font = response.json()["branding"]["font"]
        assert font["source"] == "upload"
        assert font["family"] == "Inria Sans"
        assert font["slug"] == "inria-sans"
        assert font["weights"] == ["400", "700"]

    def test_rejects_an_unsafe_family_name(self, authenticated_client):
        """✅ The family is interpolated into a <style> block, so it stays alphanumeric."""
        response = authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": 'Evil";}</style><script>alert(1)</script>'},
            files={"weight_400": ("f.ttf", io.BytesIO(b"x"), "font/ttf")},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rejects_a_non_font_extension(self, authenticated_client):
        """✅ Only real font extensions are stored."""
        response = authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("font.exe", io.BytesIO(b"x"), "application/octet-stream")},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rejects_an_upload_with_no_weights(self, authenticated_client):
        """✅ A family name with no files would produce unusable @font-face rules."""
        response = authenticated_client.post(FONT_ENDPOINT, data={"family": "Inria Sans"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_reupload_drops_weights_that_were_not_resupplied(self, authenticated_client):
        """✅ Re-uploading a narrower set of weights replaces, not merges.

        Merging would leave @font-face rules claiming weights whose files the
        org just removed.
        """
        authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={
                "weight_300": ("f300.ttf", io.BytesIO(b"ttf"), "font/ttf"),
                "weight_400": ("f400.ttf", io.BytesIO(b"ttf"), "font/ttf"),
            },
        )
        response = authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("f400.ttf", io.BytesIO(b"ttf"), "font/ttf")},
        )

        assert response.json()["branding"]["font"]["weights"] == ["400"]

    def test_reupload_in_another_format_does_not_strand_the_old_file(self, authenticated_client):
        """✅ Sparing by weight alone orphaned the previous extension's file.

        Re-uploading 400 as .woff2 writes a different filename, so the .ttf has
        to go even though weight 400 is still configured.
        """
        authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("f.ttf", io.BytesIO(b"old-ttf"), "font/ttf")},
        )
        response = authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("f.woff2", io.BytesIO(b"new-woff2"), "font/woff2")},
        )

        font = response.json()["branding"]["font"]
        assert font["extensions"] == {"400": ".woff2"}

    def test_reupload_keeps_serving_a_weight_it_resupplied(self, authenticated_client):
        """✅ The cleanup of dropped weights must not delete the kept ones."""
        authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={
                "weight_300": ("f300.ttf", io.BytesIO(b"three-hundred"), "font/ttf"),
                "weight_400": ("f400.ttf", io.BytesIO(b"four-hundred"), "font/ttf"),
            },
        )
        authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("f400.ttf", io.BytesIO(b"four-hundred"), "font/ttf")},
        )

        response = authenticated_client.get(
            f"{ASSETS_ENDPOINT}/font-400", params={"slug": "inria-sans"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"four-hundred"

    def test_clearing_an_upload_deletes_its_files(self, authenticated_client):
        """✅ Clearing goes through PATCH for both sources, and still cleans storage.

        There is no DELETE for the font: `font: null` expresses it, and a
        second route doing the same job would be one more thing to keep in step.
        """
        authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("f.ttf", io.BytesIO(b"ttf"), "font/ttf")},
        )
        cleared = authenticated_client.patch(SETTINGS_ENDPOINT, json={"branding": {"font": None}})

        assert cleared.json()["branding"]["font"] is None

        response = authenticated_client.get(
            f"{ASSETS_ENDPOINT}/font-400", params={"slug": "inria-sans"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBrandingAssets:
    """GET /organizations/settings/branding/assets/{asset}"""

    def test_serves_the_uploaded_favicon(self, authenticated_client):
        """✅ The bytes come back with the stored content type."""
        authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.png", io.BytesIO(_png()), "image/png")},
        )
        response = authenticated_client.get(f"{ASSETS_ENDPOINT}/favicon")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == _png()
        assert response.headers["content-type"] == "image/png"

    def test_favicon_carries_hardening_headers(self, authenticated_client):
        """✅ An uploaded SVG is same-origin, so it is served sandboxed and nosniff."""
        authenticated_client.post(
            FAVICON_ENDPOINT,
            files={"file": ("icon.png", io.BytesIO(_png()), "image/png")},
        )
        response = authenticated_client.get(f"{ASSETS_ENDPOINT}/favicon")

        assert response.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in response.headers["content-security-policy"]

    def test_missing_favicon_is_404(self, authenticated_client):
        """✅ No favicon configured is a 404, which is what makes the proxy fall back."""
        authenticated_client.delete(FAVICON_ENDPOINT)
        response = authenticated_client.get(f"{ASSETS_ENDPOINT}/favicon")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_font_slug_mismatch_is_404(self, authenticated_client):
        """✅ A stale @font-face URL must not be served the current font's bytes."""
        authenticated_client.post(
            FONT_ENDPOINT,
            data={"family": "Inria Sans"},
            files={"weight_400": ("f.ttf", io.BytesIO(b"ttf"), "font/ttf")},
        )
        response = authenticated_client.get(
            f"{ASSETS_ENDPOINT}/font-400", params={"slug": "some-other-font"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_asset_is_404(self, authenticated_client):
        """✅ The asset name is an allowlist, not a path into storage."""
        response = authenticated_client.get(f"{ASSETS_ENDPOINT}/../../secrets")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_authentication(self, client):
        """🔐 Branding assets are resolved from the caller's own organization."""
        response = client.get(f"{ASSETS_ENDPOINT}/favicon")

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

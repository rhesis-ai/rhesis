"""
🎨 Organization settings schema validation

The read/write asymmetry is the point of these tests: writes reject anything
malformed so the settings form can show an error, while reads tolerate keys
this version does not know about so an older pod never 500s on a blob a newer
one wrote.

Run with: python -m pytest tests/backend/schemas/test_organization_settings.py -v
"""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.organization_settings import (
    BrandingFont,
    BrandingGoogleFont,
    BrandingSettings,
    BrandingSettingsUpdate,
    OrganizationSettings,
    OrganizationSettingsUpdate,
)


class TestWritesAreStrict:
    @pytest.mark.parametrize("color", ["#fff", "6A1B9A", "rebeccapurple", "#00zz33", "#6A1B9A0"])
    def test_rejects_a_malformed_colour(self, color):
        """✅ Only the 6-digit hex form MUI's colour manipulators can parse."""
        with pytest.raises(ValidationError):
            BrandingSettingsUpdate(primary_color=color)

    def test_normalizes_a_valid_colour(self):
        """✅ Case and surrounding whitespace are normalised on the way in."""
        assert BrandingSettingsUpdate(primary_color=" #6a1b9a ").primary_color == "#6A1B9A"

    def test_treats_an_empty_colour_as_cleared(self):
        """✅ An empty string from a cleared form field means "unset", not invalid."""
        assert BrandingSettingsUpdate(primary_color="  ").primary_color is None

    def test_rejects_an_overlong_product_name(self):
        """✅ 60 characters is what keeps a browser tab title readable."""
        with pytest.raises(ValidationError):
            BrandingSettingsUpdate(product_name="x" * 61)

    def test_rejects_an_unknown_field(self):
        """✅ A typo in a PATCH body is an error, not a silently ignored no-op."""
        with pytest.raises(ValidationError):
            BrandingSettingsUpdate(primaryColour="#6A1B9A")

    def test_favicon_is_not_writable(self):
        """✅ The favicon is bytes in storage, so only its upload endpoint writes it.

        A writable `path` here would let a caller aim the asset endpoint at
        another organization's storage prefix.
        """
        assert "favicon" not in BrandingSettingsUpdate.model_fields

    def test_font_is_writable_only_as_a_google_family(self):
        """✅ A Google font is config, so PATCH sets it; an upload is bytes, so it cannot.

        `BrandingGoogleFont` has no slug, weights or paths to fill in, which is
        what keeps the storage-aiming hole closed while still allowing the
        Google option.
        """
        assert set(BrandingGoogleFont.model_fields) == {"source", "family"}

    def test_rejects_an_upload_shaped_font(self):
        """✅ `source` is pinned to 'google', so an upload cannot ride in a PATCH."""
        with pytest.raises(ValidationError):
            BrandingSettingsUpdate(
                font={"source": "upload", "family": "Inria Sans", "slug": "inria-sans"}
            )

    def test_accepts_a_google_font(self):
        """✅ The shape the settings form actually sends."""
        update = BrandingSettingsUpdate(font={"source": "google", "family": "Roboto"})

        assert update.font is not None
        assert update.font.family == "Roboto"

    def test_patch_dump_carries_only_what_was_sent(self):
        """✅ `exclude_unset` is what makes the server-side deep merge partial."""
        update = OrganizationSettingsUpdate(branding={"secondary_color": "#123456"})

        assert update.model_dump(exclude_unset=True, mode="json") == {
            "branding": {"secondary_color": "#123456"}
        }

    def test_patch_dump_keeps_an_explicit_null(self):
        """✅ An explicit null must survive the dump — it is how a field is cleared."""
        update = OrganizationSettingsUpdate(branding={"primary_color": None})

        assert update.model_dump(exclude_unset=True, mode="json") == {
            "branding": {"primary_color": None}
        }


class TestFontDescriptor:
    def test_sorts_and_deduplicates_weights(self):
        """✅ A stable order keeps the generated @font-face block deterministic."""
        font = BrandingFont(family="Inria Sans", slug="inria-sans", weights=["700", "300", "700"])

        assert font.weights == ["300", "700"]

    def test_rejects_an_unsupported_weight(self):
        """✅ Only the three weights the theme remaps onto are stored."""
        with pytest.raises(ValidationError):
            BrandingFont(family="Inria Sans", slug="inria-sans", weights=["500"])

    @pytest.mark.parametrize(
        "family",
        ['Evil";}</style><script>alert(1)</script>', "Font {Name}", "Font 'Name'"],
    )
    def test_rejects_an_unsafe_family_name(self, family):
        """✅ The family is interpolated into a <style> block in the page head."""
        with pytest.raises(ValidationError):
            BrandingFont(family=family, slug="x", weights=["400"])

    def test_rejects_an_empty_weight_list(self):
        """✅ A font with no files would emit @font-face rules pointing nowhere."""
        with pytest.raises(ValidationError):
            BrandingFont(family="Inria Sans", slug="inria-sans", weights=[])


class TestReadsAreLenient:
    def test_branding_ignores_an_unknown_key(self):
        """✅ A field written by a newer version is dropped, not fatal."""
        branding = BrandingSettings(primary_color="#6A1B9A", logo_position="left")

        assert branding.primary_color == "#6A1B9A"

    def test_settings_ignores_an_unknown_section(self):
        """✅ Same for a whole section — this blob is serialized on every org read."""
        settings = OrganizationSettings(
            version=1, branding={"product_name": "Acme"}, notifications={"digest": "weekly"}
        )

        assert settings.branding.product_name == "Acme"

    def test_font_descriptor_ignores_an_unknown_key(self):
        """✅ Descriptors are read back through BrandingSettings, so they match."""
        font = BrandingFont(
            family="Inria Sans",
            slug="inria-sans",
            weights=["400"],
            variable_axes=["wght"],
        )

        assert font.weights == ["400"]

    def test_defaults_to_an_empty_branding_section(self):
        """✅ An org that has never touched branding still reads cleanly."""
        assert OrganizationSettings().branding.primary_color is None

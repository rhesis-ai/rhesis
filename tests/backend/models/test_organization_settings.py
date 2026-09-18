"""
🎨 OrganizationSettingsManager unit tests

Covers the manager in isolation from FastAPI: default shape, deep merge,
clearing, the branding accessor, and auto-persistence back to the column.

Run with: python -m pytest tests/backend/models/test_organization_settings.py -v
"""

from rhesis.backend.app.models.organization_settings import OrganizationSettingsManager


class _FakeOrganization:
    """Stands in for an Organization row, to observe auto-persistence."""

    def __init__(self, settings=None):
        self.organization_settings = settings


class TestDefaults:
    def test_none_becomes_the_default_shape(self):
        """✅ A row written before this column existed still reads sensibly."""
        manager = OrganizationSettingsManager(None)

        assert manager.raw == {"version": 1, "branding": {}, "display": {}}

    def test_display_reads_as_unset_on_an_old_row(self):
        """✅ No currency chosen means costs show in the one they are stored in."""
        manager = OrganizationSettingsManager(None)

        assert manager.display.currency is None

    def test_display_survives_a_row_that_predates_the_section(self):
        """✅ A settings blob written before display existed still reads."""
        manager = OrganizationSettingsManager({"version": 1, "branding": {}})

        assert manager.display.currency is None

    def test_empty_branding_accessor_returns_none_per_field(self):
        """✅ Unset fields read as None so callers fall back to the env vars."""
        branding = OrganizationSettingsManager(None).branding

        assert branding.primary_color is None
        assert branding.secondary_color is None
        assert branding.product_name is None
        assert branding.favicon is None
        assert branding.font is None


class TestUpdate:
    def test_deep_merges_nested_sections(self):
        """✅ Updating one branding field leaves its siblings alone."""
        manager = OrganizationSettingsManager(
            {"version": 1, "branding": {"primary_color": "#112233", "product_name": "Acme"}}
        )

        manager.update({"branding": {"product_name": "Acme Corp"}})

        assert manager.branding.primary_color == "#112233"
        assert manager.branding.product_name == "Acme Corp"

    def test_explicit_none_clears_a_field(self):
        """✅ Clearing is how a field reverts to the deployment default."""
        manager = OrganizationSettingsManager(
            {"version": 1, "branding": {"primary_color": "#112233"}}
        )

        manager.update({"branding": {"primary_color": None}})

        assert manager.branding.primary_color is None

    def test_replaces_a_descriptor_wholesale(self):
        """✅ A font or favicon is one value, not a section to merge into.

        Merging let a previous upload's `extensions` and `sha256` entries
        survive a replacement that no longer has those files, so the descriptor
        advertised weights whose bytes had just been deleted.
        """
        manager = OrganizationSettingsManager(
            {
                "version": 1,
                "branding": {
                    "font": {
                        "source": "upload",
                        "family": "Old",
                        "slug": "old",
                        "weights": ["300", "400"],
                        "extensions": {"300": ".ttf", "400": ".ttf"},
                        "sha256": {"300": "aaa", "400": "bbb"},
                    }
                },
            }
        )

        manager.update(
            {
                "branding": {
                    "font": {
                        "source": "upload",
                        "family": "Old",
                        "slug": "old",
                        "weights": ["400"],
                        "extensions": {"400": ".woff2"},
                        "sha256": {"400": "ccc"},
                    }
                }
            }
        )

        font = manager.branding.font
        assert font["extensions"] == {"400": ".woff2"}
        assert font["sha256"] == {"400": "ccc"}

    def test_replaces_the_favicon_descriptor_too(self):
        """✅ Same rule for the favicon: a PNG replaced by an SVG keeps no size."""
        manager = OrganizationSettingsManager(
            {
                "version": 1,
                "branding": {
                    "favicon": {"path": "a.png", "sha256": "aaa", "width": 512, "height": 512}
                },
            }
        )

        manager.update({"branding": {"favicon": {"path": "a.svg", "sha256": "bbb"}}})

        assert manager.branding.favicon == {"path": "a.svg", "sha256": "bbb"}

    def test_still_merges_ordinary_nested_sections(self):
        """✅ Only the descriptors are atomic; the rest merges as before."""
        manager = OrganizationSettingsManager(
            {"version": 1, "branding": {"primary_color": "#112233", "product_name": "Acme"}}
        )

        manager.update({"branding": {"product_name": "Acme Corp"}})

        assert manager.branding.primary_color == "#112233"
        assert manager.branding.product_name == "Acme Corp"

    def test_a_complete_descriptor_overwrites_every_stale_key(self):
        """✅ What the router actually sends, and the outcome it relies on."""
        manager = OrganizationSettingsManager(
            {
                "version": 1,
                "branding": {
                    "font": {
                        "source": "upload",
                        "family": "Old",
                        "slug": "old",
                        "weights": ["300", "400"],
                    }
                },
            }
        )

        manager.update(
            {
                "branding": {
                    "font": {
                        "source": "google",
                        "family": "New",
                        "slug": None,
                        "weights": [],
                    }
                }
            }
        )

        assert manager.branding.font == {
            "source": "google",
            "family": "New",
            "slug": None,
            "weights": [],
        }

    def test_leaves_unrelated_sections_untouched(self):
        """✅ Branding edits must not disturb a future sibling section."""
        manager = OrganizationSettingsManager(
            {"version": 1, "branding": {}, "notifications": {"digest": "weekly"}}
        )

        manager.update({"branding": {"product_name": "Acme"}})

        assert manager.raw["notifications"] == {"digest": "weekly"}


class TestAutoPersistence:
    def test_update_writes_back_to_the_organization(self):
        """✅ Updating through `organization.settings` persists without a second assignment."""
        org = _FakeOrganization({"version": 1, "branding": {}})
        manager = OrganizationSettingsManager(org.organization_settings, organization_instance=org)

        manager.update({"branding": {"product_name": "Acme"}})

        assert org.organization_settings["branding"]["product_name"] == "Acme"

    def test_update_without_an_organization_does_not_raise(self):
        """✅ The manager is usable standalone, e.g. in scripts and tests."""
        manager = OrganizationSettingsManager(None)

        manager.update({"branding": {"product_name": "Acme"}})

        assert manager.branding.product_name == "Acme"

"""Organization Settings Manager - centralized access to org-level preferences.

The organization-level mirror of :class:`UserSettingsManager`: a single JSONB
column holding every org preference, so adding one needs no migration. Branding
(white-label colours, product name, favicon, font) is its first section.

Distinct from ``Organization.sso_config``, which is deliberately opaque to core
and owned by the EE licensing layer. Everything here is core-owned and
validated by ``schemas/organization_settings.py`` on write.
"""

from typing import TYPE_CHECKING, Optional

# Avoid circular imports
if TYPE_CHECKING:
    from rhesis.backend.app.models.organization import Organization


class OrganizationSettingsManager:
    """
    Centralized manager for accessing and updating organization settings.

    When created with an organization instance reference, updates are
    automatically persisted to the database.

    Usage:
        org = db.query(Organization).get(org_id)

        # Access branding settings
        colour = org.settings.branding.primary_color
        name = org.settings.branding.product_name

        # Update settings (auto-persists when created from Organization.settings)
        org.settings.update({"branding": {"primary_color": "#6A1B9A"}})
    """

    def __init__(
        self,
        settings_dict: dict,
        organization_instance: Optional["Organization"] = None,
    ):
        """
        Initialize settings manager with an organization's settings dictionary.

        Args:
            settings_dict: The organization_settings JSONB data from database
            organization_instance: Optional Organization reference for auto-persistence
        """
        self._data = settings_dict or self._default_settings()
        self._organization = organization_instance

    #: Dotted paths whose value is one indivisible descriptor, replaced rather
    #: than merged. Both point at files in object storage: merging would let a
    #: previous upload's ``extensions`` and ``sha256`` entries survive a
    #: replacement that no longer has those files, leaving the descriptor
    #: advertising weights that were just deleted.
    ATOMIC_PATHS = frozenset({"branding.favicon", "branding.font"})

    @staticmethod
    def _default_settings() -> dict:
        """Return default settings structure."""
        return {"version": 1, "branding": {}, "display": {}}

    @property
    def raw(self) -> dict:
        """Get raw settings dictionary."""
        return self._data

    @property
    def branding(self) -> "BrandingSettingsAccessor":
        """Access white-label branding settings."""
        return BrandingSettingsAccessor(self._data.get("branding") or {})

    @property
    def display(self) -> "DisplaySettingsAccessor":
        """Access how figures are shown across the organization."""
        return DisplaySettingsAccessor(self._data.get("display") or {})

    def update(self, updates: dict) -> dict:
        """
        Deep merge updates into settings.

        When the manager has an organization reference, changes are
        automatically persisted to the database. Otherwise, manual persistence
        is required.

        An explicit ``None`` clears a value rather than being ignored, which is
        how a field reverts to the deployment-wide env-var default.

        Args:
            updates: Dictionary of settings to update

        Returns:
            Updated settings dictionary
        """
        self._data = self._deep_merge(self._data, updates)

        # Auto-persist if we have an organization reference
        if self._organization is not None:
            self._organization.organization_settings = self._data

        return self._data

    @classmethod
    def _deep_merge(cls, base: dict, updates: dict, path: str = "") -> dict:
        """Deep merge two dictionaries, except at :attr:`ATOMIC_PATHS`."""
        result = base.copy()
        for key, value in updates.items():
            child = f"{path}.{key}" if path else key
            if (
                child not in cls.ATOMIC_PATHS
                and key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = cls._deep_merge(result[key], value, child)
            else:
                result[key] = value
        return result


class BrandingSettingsAccessor:
    """Accessor for white-label branding settings.

    Every field is optional. An unset field means "fall back to the
    deployment-wide ``BRAND_*`` env var, then to the Rhesis default" — the
    frontend resolves that chain in ``config/branding.ts``.
    """

    def __init__(self, branding_settings: dict):
        self._data = branding_settings

    @property
    def primary_color(self) -> Optional[str]:
        """Primary brand colour as a 6-digit hex string (e.g. ``#6A1B9A``)."""
        return self._data.get("primary_color")

    @property
    def secondary_color(self) -> Optional[str]:
        """Secondary/CTA colour as a 6-digit hex string."""
        return self._data.get("secondary_color")

    @property
    def product_name(self) -> Optional[str]:
        """Product name shown in page titles and the sidebar."""
        return self._data.get("product_name")

    @property
    def favicon(self) -> Optional[dict]:
        """Stored favicon descriptor: ``{path, content_type, filename, sha256}``."""
        return self._data.get("favicon") or None

    @property
    def font(self) -> Optional[dict]:
        """Stored font descriptor: ``{family, slug, weights, content_types}``."""
        return self._data.get("font") or None

    @property
    def all(self) -> dict:
        """Get all branding settings as a dictionary."""
        return self._data


class DisplaySettingsAccessor:
    """Accessor for organization-wide display preferences."""

    def __init__(self, display_settings: dict):
        self._data = display_settings

    @property
    def currency(self) -> Optional[str]:
        """Currency costs are shown in, for members with no personal override.

        None means the organization has expressed no preference, and callers
        fall back to the currency costs are stored in.
        """
        return self._data.get("currency")

"""EE feature registry and license gate.

Every "is EE feature X available for this organization?" question flows
through :meth:`FeatureRegistry.is_available`. This is the single extension
point where license validation plugs in (by swapping
:class:`DefaultLicenseProvider` for :class:`JwtLicenseProvider` via
:meth:`FeatureRegistry.set_license_provider`).

A feature is available iff ALL three conditions hold (fail-closed order):

1. **Registered** — added to the registry via :meth:`FeatureRegistry.register`,
   which happens inside ``ee/backend/src/rhesis/backend/ee/__init__.py:bootstrap()``.
   Unknown names return ``False``.
2. **Licensed** — the active :class:`LicenseProvider` allows it for the
   current org. :class:`DefaultLicenseProvider` (no ``RHESIS_LICENSE`` set)
   allows everything; :class:`JwtLicenseProvider` allows only features listed
   in the signed JWT.
3. **Runtime check passes** — optional callable on :class:`Feature` (e.g.
   ``SSO_ENCRYPTION_KEY`` must be configured); invoked on every availability
   check.

:class:`FeatureName` is the canonical source of truth for EE feature
identifiers. Add new members here when adding a new EE feature, then register
the corresponding :class:`Feature` in ``ee/__init__.py:bootstrap()``.
Because ``FeatureName`` inherits from ``str``, members serialize transparently
to JSON and compare equal to their raw string values (``FeatureName.SSO == "sso"``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Protocol, Union

from rhesis.backend.app.models.organization import Organization


class FeatureName(str, Enum):
    """Canonical identifiers for EE features.

    Inheriting from ``str`` means members compare equal to their value
    (``FeatureName.SSO == "sso"``) and FastAPI serializes them to their
    raw string over the wire.
    """

    SSO = "sso"


# Accept either the enum or its raw string value so dynamic call sites
# (wire deserialization, tests, orgless callers) remain ergonomic.
# Unknown strings fail closed in :meth:`FeatureRegistry.is_available`.
FeatureNameLike = Union[FeatureName, str]


@dataclass(frozen=True)
class Feature:
    """Declarative metadata for an EE feature.

    :param name: canonical :class:`FeatureName` identifier.
    :param display_name: human-readable label for the UI.
    :param runtime_check: optional system-level precondition (e.g. a required
        env var); invoked on every availability check.
    :param description: free-form description shown in the features endpoint.
    """

    name: FeatureName
    display_name: str
    runtime_check: Optional[Callable[[], bool]] = field(default=None, compare=False)
    description: str = ""


class LicenseProvider(Protocol):
    """Pluggable license validator.

    Implementations decide whether a specific EE feature is licensed for a
    given organization. Only one implementation is active per process,
    installed via :meth:`FeatureRegistry.set_license_provider`.
    """

    def allows_feature(self, feature: Feature, org: Organization) -> bool: ...
    def info(self) -> dict: ...


class DefaultLicenseProvider:
    """No-license provider — allows all registered EE features for every org.

    Active when ``RHESIS_LICENSE`` is not set. Intended for local development
    with the ``ee`` package installed but no license key configured.

    Replaced at startup by :class:`JwtLicenseProvider` when a valid
    ``RHESIS_LICENSE`` JWT is present.
    """

    def allows_feature(self, feature: Feature, org: Organization) -> bool:
        return True

    def info(self) -> dict:
        return {"edition": "community", "licensed": False}


class FeatureRegistry:
    """Singleton registry of EE features.

    Holds the installed :class:`LicenseProvider` and the map of registered
    :class:`Feature` instances. All queries resolve through
    :meth:`is_available`, which combines registration, license validation, and
    runtime checks in fail-closed order.
    """

    _features: dict[FeatureName, Feature] = {}
    _license: LicenseProvider = DefaultLicenseProvider()

    @classmethod
    def register(cls, feature: Feature) -> None:
        """Register an EE feature. Idempotent — later registrations override."""
        cls._features[feature.name] = feature

    @classmethod
    def set_license_provider(cls, provider: LicenseProvider) -> None:
        """Install the license provider. Call once at bootstrap."""
        cls._license = provider

    @staticmethod
    def _coerce(name: FeatureNameLike) -> Optional[FeatureName]:
        """Coerce *name* to a :class:`FeatureName`, returning ``None`` on failure."""
        if isinstance(name, FeatureName):
            return name
        try:
            return FeatureName(name)
        except ValueError:
            return None

    @classmethod
    def is_available(
        cls,
        name: FeatureNameLike,
        org: Optional[Organization] = None,
    ) -> bool:
        """Return ``True`` iff the feature is registered, licensed for *org*,
        and passes its runtime check.

        When *org* is ``None`` the license check is skipped (useful for tests
        and internal checks that have no organisation context).
        """
        key = cls._coerce(name)
        if key is None:
            return False
        feature = cls._features.get(key)
        if feature is None:
            return False
        if org is not None and not cls._license.allows_feature(feature, org):
            return False
        if feature.runtime_check is not None and not feature.runtime_check():
            return False
        return True

    @classmethod
    def enabled_features(cls, org: Optional[Organization] = None) -> list[Feature]:
        """Return all EE features currently available for *org*."""
        return [f for f in cls._features.values() if cls.is_available(f.name, org)]

    @classmethod
    def license_info(cls) -> dict:
        """Opaque license metadata for diagnostics and UI badges."""
        return cls._license.info()

    @classmethod
    def reset(cls) -> None:
        """Clear the registry and reinstall the default provider. For tests only."""
        cls._features = {}
        cls._license = DefaultLicenseProvider()


__all__ = [
    "DefaultLicenseProvider",
    "Feature",
    "FeatureName",
    "FeatureNameLike",
    "FeatureRegistry",
    "LicenseProvider",
]

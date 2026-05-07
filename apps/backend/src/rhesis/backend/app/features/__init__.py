"""EE feature registry and license gate.

Every "is EE feature X available for this organization?" question flows
through :meth:`FeatureRegistry.is_available`. This is the single extension
point where license validation plugs in (by swapping
:class:`DefaultLicenseProvider` for :class:`JwtLicenseProvider` via
:meth:`FeatureRegistry.set_license_provider`).

Two query methods, both fail-closed:

- :meth:`is_registered` — registered + runtime check passes. Does NOT consult
  the license provider. Use this for early-bailout checks before an
  organization has been resolved (e.g. inside an OIDC callback before
  validating the signed state).
- :meth:`is_available` — registered + license provider allows it for the
  given organization + runtime check passes. The organization argument is
  required; this is the call you want for any per-tenant gating.

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

    Equality is by ``name`` only; the registry guarantees one entry per name,
    so display labels and descriptions are mutable presentation details that
    must not influence identity. Without this, two ``Feature`` instances
    differing only in ``description`` would compare unequal, breaking
    idempotent re-registration.

    :param name: canonical :class:`FeatureName` identifier.
    :param display_name: human-readable label for the UI.
    :param runtime_check: optional system-level precondition (e.g. a required
        env var); invoked on every availability check.
    :param description: free-form description shown in the features endpoint.
    """

    name: FeatureName
    display_name: str = field(default="", compare=False)
    runtime_check: Optional[Callable[[], bool]] = field(default=None, compare=False)
    description: str = field(default="", compare=False)


class LicenseProvider(Protocol):
    """Pluggable license validator.

    Implementations decide whether a specific EE feature is licensed for a
    given organization. Only one implementation is active per process,
    installed via :meth:`FeatureRegistry.set_license_provider`.
    """

    def allows_feature(self, feature: Feature, org: Organization) -> bool: ...
    def info(self) -> dict: ...


class DefaultLicenseProvider:
    """Permissive provider — allows every registered EE feature for every org.

    Active when ``RHESIS_LICENSE`` is not set. Intended for local development
    with the ``ee`` package installed but no license key configured. In
    production, :class:`JwtLicenseProvider` replaces this and restricts
    access to features listed in the signed JWT.
    """

    def allows_feature(self, feature: Feature, org: Organization) -> bool:
        return True

    def info(self) -> dict:
        # ``edition: dev`` (rather than ``community``) communicates that the EE
        # package is loaded but unlicensed, which matters for diagnostic UI.
        return {"edition": "dev", "licensed": False}


class FeatureRegistry:
    """Singleton registry of EE features.

    Holds the installed :class:`LicenseProvider` and the map of registered
    :class:`Feature` instances. Two queries: :meth:`is_registered` (no
    license check) and :meth:`is_available` (full check, requires org).
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
    def is_registered(cls, name: FeatureNameLike) -> bool:
        """Return ``True`` iff the feature is registered and its runtime check passes.

        Does NOT consult the license provider. Use as an early bailout when
        an organization has not yet been resolved — for example inside an
        OIDC callback before the signed state has been validated. License
        enforcement happens via :meth:`is_available` (or the
        ``require_feature`` route dependency) once the org is in hand.
        """
        key = cls._coerce(name)
        if key is None:
            return False
        feature = cls._features.get(key)
        if feature is None:
            return False
        if feature.runtime_check is not None and not feature.runtime_check():
            return False
        return True

    @classmethod
    def is_available(cls, name: FeatureNameLike, org: Optional[Organization]) -> bool:
        """Return ``True`` iff *name* is registered, licensed for *org*, and
        passes its runtime check.

        Organization is required: feature gating without org context cannot
        consult the license provider, which is precisely what
        :meth:`is_registered` exists for. Passing ``None`` fails closed —
        a user with no associated organization is never granted EE features.
        """
        if org is None:
            return False
        key = cls._coerce(name)
        if key is None:
            return False
        feature = cls._features.get(key)
        if feature is None:
            return False
        if not cls._license.allows_feature(feature, org):
            return False
        if feature.runtime_check is not None and not feature.runtime_check():
            return False
        return True

    @classmethod
    def enabled_features(cls, org: Optional[Organization]) -> list[Feature]:
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

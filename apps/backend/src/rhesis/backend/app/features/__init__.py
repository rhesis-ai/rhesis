"""EE feature registry and license gate.

Every "is EE feature X available for this organization?" question flows
through :meth:`FeatureRegistry.is_available`. This is the single extension
point where license validation plugs in (by swapping
:class:`DefaultLicenseProvider` for :class:`JwtLicenseProvider` via
:meth:`FeatureRegistry.set_license_provider`).

Three query tiers, all fail-closed:

- :meth:`is_registered` — in the registry. Does NOT consult the license
  provider or runtime checks. Use as an early bailout when an organization
  has not yet been resolved (e.g. inside an OIDC callback).
- :meth:`is_licensed` — registered + license provider allows it for the
  given organization. Does NOT run the runtime check. Use for UI visibility
  (the ``GET /features`` endpoint) so licensed features always appear even
  when their backing infrastructure is not yet configured.
- :meth:`is_available` — registered + licensed + runtime check passes.
  The strictest gate; use for route-level enforcement via
  ``require_feature`` / ``has_feature``.

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

    ``__str__`` is overridden so ``str(FeatureName.SSO)`` returns ``"sso"``
    on Python 3.10–3.11 (where the default Enum.__str__ returns
    ``"FeatureName.SSO"`` for str+Enum subclasses, not the value).
    Python 3.11+ StrEnum has this right by default; this keeps parity on 3.10.
    """

    def __str__(self) -> str:
        return self.value

    SSO = "sso"
    API_CLIENTS = "api_clients"
    #: Full RBAC: project-role overrides + custom roles (Phase 2, SP7–SP9).
    RBAC = "rbac"


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
    """Permissive provider — allows all EE features for every org.

    Active when ``RHESIS_LICENSE`` is not set. Intended for local development
    with the ``ee`` package installed but no license key configured. In
    production, :class:`JwtLicenseProvider` replaces this and restricts
    access to features listed in the signed JWT.

    RBAC was previously excluded until the ``e1f2a3b4c5d6`` backfill migration
    seeded ``organization_member`` rows for every existing user. Now that the
    backfill migration ships with the feature, RBAC is allowed by default so
    that the EE developer workflow does not require a separate license step.
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
    :class:`Feature` instances. Three query tiers: :meth:`is_registered`
    (cheapest), :meth:`is_licensed` (license only, no runtime check), and
    :meth:`is_available` (strictest, includes runtime check).
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
        """Return ``True`` iff the feature is in the registry.

        Does NOT consult the license provider or run the runtime check.
        Use as an early bailout when an organization has not yet been
        resolved — for example inside an OIDC callback before the signed
        state has been validated.
        """
        key = cls._coerce(name)
        if key is None:
            return False
        return key in cls._features

    @classmethod
    def is_licensed(cls, name: FeatureNameLike, org: Optional[Organization]) -> bool:
        """Return ``True`` iff *name* is registered and licensed for *org*.

        Does NOT run the feature's runtime check. Use this for UI
        visibility decisions (e.g. the ``GET /features`` endpoint) so
        that licensed features always appear even when their backing
        infrastructure is not yet configured.
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
        return True

    @classmethod
    def is_available(cls, name: FeatureNameLike, org: Optional[Organization]) -> bool:
        """Return ``True`` iff *name* is registered, licensed for *org*, and
        passes its runtime check.

        This is the strictest gate. Use for route-level enforcement via
        ``require_feature`` / ``has_feature``. For UI visibility, use
        :meth:`is_licensed` instead.
        """
        if not cls.is_licensed(name, org):
            return False
        feature = cls._features[cls._coerce(name)]  # type: ignore[index]
        if feature.runtime_check is not None and not feature.runtime_check():
            return False
        return True

    @classmethod
    def licensed_features(cls, org: Optional[Organization]) -> list[Feature]:
        """Return all EE features licensed for *org* (ignoring runtime checks)."""
        return [f for f in cls._features.values() if cls.is_licensed(f.name, org)]

    @classmethod
    def enabled_features(cls, org: Optional[Organization]) -> list[Feature]:
        """Return all EE features fully available for *org* (including runtime checks)."""
        return [f for f in cls._features.values() if cls.is_available(f.name, org)]

    @classmethod
    def feature_warnings(cls, org: Optional[Organization]) -> dict[str, str]:
        """Return warnings for features licensed but not operationally ready."""
        warnings: dict[str, str] = {}
        for f in cls.licensed_features(org):
            if f.runtime_check is not None and not f.runtime_check():
                warnings[f.name.value] = (
                    f"{f.display_name} is licensed but not yet configured. "
                    f"Contact your administrator to complete the setup."
                )
        return warnings

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

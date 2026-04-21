"""Central feature registry and license gate.

Every "is feature X available for this organization?" question in the
codebase should flow through :meth:`FeatureRegistry.is_available`. This
is the single extension point where real license validation will slot
in later (by swapping :class:`DefaultLicenseProvider` for a real
implementation via :meth:`FeatureRegistry.set_license_provider`).

Today the default provider allows every registered feature. A feature
is still gated by:

- Registration: callers asking for an unknown name receive ``False``.
- Runtime preconditions: an optional ``runtime_check`` callable on the
  feature (for SSO, this is :func:`is_sso_encryption_available`).

The enum :class:`FeatureName` is the canonical source of truth for
feature identifiers. Add new members here before registering or
gating against them. Because ``FeatureName`` inherits from ``str``,
members serialize transparently to JSON and compare equal to their
raw string values (``FeatureName.SSO == "sso"``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Protocol, Union

from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.subscription import SubscriptionPlan


class FeatureName(str, Enum):
    """Canonical names of gated features.

    Inheriting from ``str`` means members compare equal to their value
    (``FeatureName.SSO == "sso"``) and FastAPI serializes them to their
    raw string over the wire. Add new members here before registering
    the corresponding :class:`Feature` in ``features_bootstrap``.
    """

    SSO = "sso"


# Accept either the enum or its raw string value. Dynamic call sites
# (wire deserialization, tests, orgless legacy callers) remain ergonomic,
# but unknown strings safely fail closed in :meth:`FeatureRegistry.is_available`.
FeatureNameLike = Union[FeatureName, str]


@dataclass(frozen=True)
class Feature:
    """Declarative metadata for a gated capability.

    :param name: canonical :class:`FeatureName` identifier
    :param display_name: human-readable label for UI
    :param min_plan: minimum subscription plan the license must allow
        (consulted by real :class:`LicenseProvider` implementations;
        ignored by :class:`DefaultLicenseProvider`)
    :param runtime_check: optional system-level precondition (e.g. an
        encryption key being configured); invoked on every
        availability check
    :param description: free-form description
    """

    name: FeatureName
    display_name: str
    min_plan: SubscriptionPlan = SubscriptionPlan.FREE
    runtime_check: Optional[Callable[[], bool]] = None
    description: str = ""


class LicenseProvider(Protocol):
    """Pluggable license validator.

    Implementations decide whether a specific feature is licensed for a
    given organization. Only one implementation is active per process,
    installed via :meth:`FeatureRegistry.set_license_provider`.
    """

    def allows_feature(self, feature: Feature, org: Organization) -> bool: ...
    def info(self) -> dict: ...


class DefaultLicenseProvider:
    """Stub provider. Allows every registered feature for every org.

    Replace when real license validation lands:

    - validate a signed JWT from ``RHESIS_LICENSE_KEY``
    - compare ``org.subscription.plan`` to ``feature.min_plan``
    - check per-feature entitlements embedded in the license

    Only this class needs to change; all call sites flow through
    :meth:`FeatureRegistry.is_available`.
    """

    def allows_feature(self, feature: Feature, org: Organization) -> bool:
        return True

    def info(self) -> dict:
        return {"edition": "community", "licensed": False}


class FeatureRegistry:
    """Singleton registry of gated features.

    Holds the installed :class:`LicenseProvider` and the map of
    registered :class:`Feature` instances. All queries resolve through
    :meth:`is_available`, which combines registration, license
    validation, and runtime checks in fail-closed order.
    """

    _features: dict[FeatureName, Feature] = {}
    _license: LicenseProvider = DefaultLicenseProvider()

    @classmethod
    def register(cls, feature: Feature) -> None:
        """Register a feature. Idempotent (later registrations override)."""
        cls._features[feature.name] = feature

    @classmethod
    def set_license_provider(cls, provider: LicenseProvider) -> None:
        """Install the license provider. Call once at bootstrap."""
        cls._license = provider

    @staticmethod
    def _coerce(name: FeatureNameLike) -> Optional[FeatureName]:
        """Best-effort coerce ``name`` to a ``FeatureName``.

        Unknown strings return ``None``, which flows into a ``False``
        availability result upstream (fail-closed).
        """
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
        """Return ``True`` iff the feature is registered, licensed for
        ``org`` (if provided), and passes its runtime check.

        When ``org`` is ``None`` the license check is skipped. This
        preserves backward compatibility with legacy callers that had
        no organization handle; real license providers should enforce
        org presence via their own policy if needed.
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
        """Return all features currently available for ``org``."""
        return [f for f in cls._features.values() if cls.is_available(f.name, org)]

    @classmethod
    def license_info(cls) -> dict:
        """Opaque license metadata for diagnostics / UI badges."""
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

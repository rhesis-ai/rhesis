"""Usage quota registry and enforcement gate.

Every "has org X exhausted resource Y?" question flows through
:meth:`QuotaRegistry.get_limit`.  This is the single extension point
where tier-aware limit resolution plugs in (by swapping
:class:`DefaultQuotaProvider` for a config-backed provider via
:meth:`QuotaRegistry.set_quota_provider`).

:class:`QuotaResource` is the canonical source of truth for metered
resource identifiers.  Add new members here when adding a new metered
resource.  Because ``QuotaResource`` inherits from ``str``, members
serialize transparently to JSON and compare equal to their raw string
values (``QuotaResource.TEST_EXECUTIONS == "test_executions"``).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Protocol, Union

from rhesis.backend.app.models.organization import Organization


class QuotaResource(str, Enum):
    """Canonical identifiers for metered resources.

    Inheriting from ``str`` means members compare equal to their value
    and FastAPI serializes them to their raw string over the wire.

    ``__str__`` is overridden so ``str(QuotaResource.TEST_EXECUTIONS)``
    returns ``"test_executions"`` on Python 3.10-3.11 (where the default
    Enum.__str__ returns ``"QuotaResource.TEST_EXECUTIONS"`` for
    str+Enum subclasses).
    """

    def __str__(self) -> str:
        return self.value

    TEST_EXECUTIONS = "test_executions"
    TRACING_SPANS = "tracing_spans"
    TEST_GENERATION = "test_generation"
    MODEL_TOKENS = "model_tokens"
    SEATS = "seats"
    PROJECTS = "projects"
    ENDPOINTS = "endpoints"


QuotaResourceLike = Union[QuotaResource, str]


# Free-tier defaults applied when no EE quota provider is installed, and the
# safety-net catalog EE falls back to if its tier config YAML is missing or
# malformed. Exported (not underscore-prefixed) so both consumers -- and a
# test asserting the YAML's "community" entry matches -- can reference the
# same numbers instead of duplicating them.
FREE_TIER_LIMITS: dict[QuotaResource, int | None] = {
    QuotaResource.TEST_EXECUTIONS: 1_000,
    QuotaResource.TRACING_SPANS: 50_000,
    QuotaResource.TEST_GENERATION: 500,
    QuotaResource.MODEL_TOKENS: 5_000_000,
    QuotaResource.SEATS: 3,
    QuotaResource.PROJECTS: 1,
    QuotaResource.ENDPOINTS: 1,
}


def limits_to_wire(limits: dict[QuotaResource, int | None]) -> dict[str, int | None]:
    """Convert a ``QuotaResource``-keyed limits dict to string keys for the wire.

    Single conversion point for both the JWT ``lic.limits`` claim (see
    :func:`~rhesis.backend.ee.licensing.tiers.tier_to_lic_claim`) and the
    ``GET /features`` response -- both need the same enum-to-string shape.
    """
    return {str(k): v for k, v in limits.items()}


class QuotaProvider(Protocol):
    """Pluggable limit resolver.

    Implementations decide what numeric limits apply to a given
    organization for each metered resource.  Only one implementation is
    active per process, installed via
    :meth:`QuotaRegistry.set_quota_provider`.
    """

    def get_limits(self, org: Optional[Organization] = None) -> dict[QuotaResource, int | None]: ...


class DefaultQuotaProvider:
    """Returns hardcoded free-tier limits for every org.

    Active when the EE package is not installed or no license is
    configured.  In production,
    :class:`~rhesis.backend.ee.licensing.quota_provider.ConfigQuotaProvider`
    replaces this and resolves limits from the tier YAML config.
    """

    def get_limits(self, org: Optional[Organization] = None) -> dict[QuotaResource, int | None]:
        return dict(FREE_TIER_LIMITS)


class QuotaRegistry:
    """Singleton registry for quota limits.

    Holds the installed :class:`QuotaProvider`.  Callers query limits
    via :meth:`get_limit` / :meth:`get_limits`; the provider decides
    how to resolve them (hardcoded defaults vs. YAML config vs. DB).
    """

    _provider: QuotaProvider = DefaultQuotaProvider()

    @classmethod
    def set_quota_provider(cls, provider: QuotaProvider) -> None:
        """Install the quota provider.  Call once at bootstrap."""
        cls._provider = provider

    @staticmethod
    def _coerce(resource: QuotaResourceLike) -> QuotaResource:
        """Coerce *resource* to a :class:`QuotaResource`.

        :raises ValueError: if *resource* is not a known member. A
            typo'd or unrecognized resource must fail loud here -- ``None``
            already means "unlimited" downstream, so silently returning it
            for an unknown resource would grant unmetered access instead of
            surfacing the mistake.
        """
        if isinstance(resource, QuotaResource):
            return resource
        return QuotaResource(resource)

    @classmethod
    def get_limits(cls, org: Optional[Organization] = None) -> dict[QuotaResource, int | None]:
        """Return all resource limits for *org*."""
        return cls._provider.get_limits(org)

    @classmethod
    def get_limit(
        cls,
        org: Optional[Organization],
        resource: QuotaResourceLike,
    ) -> int | None:
        """Return the limit for a single *resource*, or ``None`` if unlimited.

        :raises ValueError: if *resource* is not a known :class:`QuotaResource`.
        """
        key = cls._coerce(resource)
        return cls.get_limits(org).get(key)

    @classmethod
    def reset(cls) -> None:
        """Reinstall the default provider.  For tests only."""
        cls._provider = DefaultQuotaProvider()


__all__ = [
    "DefaultQuotaProvider",
    "FREE_TIER_LIMITS",
    "QuotaProvider",
    "QuotaRegistry",
    "QuotaResource",
    "QuotaResourceLike",
    "limits_to_wire",
]

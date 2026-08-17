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

Actual enforcement (blocking a request once a limit is reached) lives in
:mod:`rhesis.backend.app.quota.enforcement`, not here -- this module only
resolves *what the limits and overage policy are*, not what to do about
them. Keeping that split means the token-usage gate in
``user_model_utils.py`` and the HTTP gate in ``auth/quota_gates.py`` share
one blocking rule instead of each re-deriving it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


class OveragePolicy(str, Enum):
    """What happens when an organization reaches a limit.

    ``HARD`` blocks at the limit. ``SOFT`` allows a configurable grace band
    past it (see :attr:`QuotaPolicy.overage_tolerance_percent`) and only
    blocks once that is exhausted, so a paying customer is warned before
    being cut off mid-work rather than after.

    Replaces the bare ``"hard"``/``"soft"`` strings previously carried on
    ``TierSpec`` and in the tier YAML, keeping resource *and* policy
    identifiers typed for the same reason (see :class:`QuotaResource`).
    """

    def __str__(self) -> str:
        return self.value

    HARD = "hard"
    SOFT = "soft"


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


@dataclass(frozen=True)
class QuotaPolicy:
    """An organization's resolved limits plus what to do when they are hit.

    :param limits: per-resource caps; ``None`` means unlimited.
    :param overage: whether reaching a limit blocks immediately
        (:attr:`OveragePolicy.HARD`) or allows a grace band
        (:attr:`OveragePolicy.SOFT`).
    :param overage_tolerance_percent: how far past a limit a ``SOFT`` tier
        may run before it hard-blocks, as a whole percent. ``0`` means no
        grace, which makes ``SOFT`` behave identically to ``HARD``.

    A percent rather than a float multiplier so the tier YAML reads as
    ``overage_tolerance_percent: 25`` instead of ``1.25``, and so
    :meth:`ceiling_for` stays integer arithmetic -- ``used`` is an integer
    count and comparing it against a float ceiling invites the usual
    floating-point boundary surprises at exactly the value that decides
    whether a customer is blocked.
    """

    limits: dict[QuotaResource, int | None] = field(default_factory=dict)
    overage: OveragePolicy = OveragePolicy.HARD
    overage_tolerance_percent: int = 0

    def ceiling_for(self, limit: Optional[int]) -> Optional[int]:
        """Return the value of ``used`` at which *limit* actually blocks.

        ``None`` (unlimited) passes straight through. For ``HARD`` -- and
        for ``SOFT`` with zero tolerance -- the ceiling is the limit itself,
        so both policies fall out of one expression with no branch at the
        call site.

        The integer division floors, so a ``SOFT`` limit small enough that
        the tolerance is worth less than one unit gets no grace band at all
        (25% of 3 floors to 0, giving ``ceiling == limit``). That is correct
        -- a fractional unit of quota is not a thing -- but it does mean a
        tier's advertised tolerance quietly stops applying below
        ``100 / tolerance_percent``. Real paid limits are far above that;
        it mostly bites when writing deliberately tiny limits for testing.
        """
        if limit is None:
            return None
        if self.overage is not OveragePolicy.SOFT:
            return limit
        return limit * (100 + self.overage_tolerance_percent) // 100


def limits_to_wire(limits: dict[QuotaResource, int | None]) -> dict[str, int | None]:
    """Convert a ``QuotaResource``-keyed limits dict to string keys for the wire.

    Single conversion point for both the JWT ``lic.limits`` claim (see
    :func:`~rhesis.backend.ee.licensing.tiers.tier_to_lic_claim`) and the
    ``GET /features`` response -- both need the same enum-to-string shape.
    """
    return {str(k): v for k, v in limits.items()}


class QuotaProvider(Protocol):
    """Pluggable limit and overage-policy resolver.

    Implementations decide what limits and overage policy apply to a given
    organization. Only one implementation is active per process, installed
    via :meth:`QuotaRegistry.set_quota_provider`.

    Deliberately a single method. An earlier version of this protocol also
    required ``get_limits()``, which meant every implementation carried two
    overlapping methods that had to agree with each other. ``QuotaPolicy``
    already carries ``limits``, so :meth:`QuotaRegistry.get_limits` derives
    from :meth:`QuotaRegistry.get_policy` instead of asking providers for it
    a second way.
    """

    def get_policy(self, org: Optional[Organization] = None) -> QuotaPolicy: ...


class DefaultQuotaProvider:
    """Returns hardcoded free-tier limits and hard enforcement for every org.

    Active when the EE package is not installed or no license is
    configured.  In production,
    :class:`~rhesis.backend.ee.licensing.quota_provider.ConfigQuotaProvider`
    replaces this and resolves the policy from the tier YAML config.
    """

    def get_policy(self, org: Optional[Organization] = None) -> QuotaPolicy:
        return QuotaPolicy(limits=dict(FREE_TIER_LIMITS))


class QuotaRegistry:
    """Singleton registry for quota policy.

    Holds the installed :class:`QuotaProvider`.  Callers query the policy
    via :meth:`get_policy`, or just the limits via :meth:`get_limit` /
    :meth:`get_limits`; the provider decides how to resolve them (hardcoded
    defaults vs. YAML config vs. DB).
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
    def get_policy(cls, org: Optional[Organization] = None) -> QuotaPolicy:
        """Return the resolved limits and overage policy for *org*."""
        return cls._provider.get_policy(org)

    @classmethod
    def get_limits(cls, org: Optional[Organization] = None) -> dict[QuotaResource, int | None]:
        """Return all resource limits for *org*.

        A thin wrapper over :meth:`get_policy` -- kept as its own method
        because ``services/usage.py`` and ``routers/features.py`` only ever
        need the limits, not the overage policy, and predate that field.
        """
        return cls.get_policy(org).limits

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
    "OveragePolicy",
    "QuotaPolicy",
    "QuotaProvider",
    "QuotaRegistry",
    "QuotaResource",
    "QuotaResourceLike",
    "limits_to_wire",
]

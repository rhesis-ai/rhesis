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

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, Union

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.models.organization import Organization

logger = logging.getLogger(__name__)


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


# Display names for user-facing copy, lowercased for use mid-sentence.
# Mirrors QUOTA_RESOURCE_LABELS in apps/frontend/src/constants/quota.ts and
# must stay in sync with it: the frontend renders the inline gates and the
# banner, this side renders the notification a quota crossing writes, and
# the two are read by the same person about the same resource.
#
# Deliberately not `resource.value.replace("_", " ")`: TEST_EXECUTIONS is
# called "test runs" throughout the product, which no mechanical transform
# of the wire value produces.
QUOTA_RESOURCE_LABELS: dict[QuotaResource, str] = {
    QuotaResource.TEST_EXECUTIONS: "test runs",
    QuotaResource.TRACING_SPANS: "tracing spans",
    QuotaResource.TEST_GENERATION: "test generation",
    QuotaResource.MODEL_TOKENS: "model tokens",
    QuotaResource.SEATS: "seats",
    QuotaResource.PROJECTS: "projects",
    QuotaResource.ENDPOINTS: "endpoints",
}


def resource_label(resource: QuotaResource) -> str:
    """Lowercase display name for *resource*, for use mid-sentence.

    Falls back to the wire value with underscores spaced out, so a resource
    added to :class:`QuotaResource` before this map catches up degrades to
    readable-but-unpolished rather than raising in a copy path.
    """
    return QUOTA_RESOURCE_LABELS.get(resource, resource.value.replace("_", " "))


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
#
# Published on the pricing page as the Free plan -- see the header comment in
# ee/.../licensing/tier_config.yaml. These must stay equal to that file's
# `community` entry (asserted by tests/backend/ee/licensing/test_tiers.py).
FREE_TIER_LIMITS: dict[QuotaResource, int | None] = {
    QuotaResource.TEST_EXECUTIONS: 500,
    QuotaResource.TRACING_SPANS: 50_000,
    QuotaResource.TEST_GENERATION: 100,
    QuotaResource.MODEL_TOKENS: 1_000_000,
    QuotaResource.SEATS: 3,
    QuotaResource.PROJECTS: 3,
    QuotaResource.ENDPOINTS: 3,
}

# Every resource explicitly set to None (unlimited). Explicit keys rather than
# an empty dict so the /features wire shape stays stable: callers always see
# all seven resource names, whether the deployment enforces quotas or not.
UNLIMITED_LIMITS: dict[QuotaResource, int | None] = {r: None for r in QuotaResource}


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

    def with_limit_overrides(self, overrides: dict[QuotaResource, int | None]) -> "QuotaPolicy":
        """Return a copy with *overrides* applied on top of :attr:`limits`.

        A **per-resource** merge, not a replacement: a resource absent from
        *overrides* keeps this policy's limit. That is what makes a partial
        override meaningful -- a bespoke deal that caps one resource must not
        silently unmeter the other six by omitting them.

        The overage policy is deliberately not overridable. A negotiated cap
        changes *what* the ceiling is, not whether the tier gets a grace band
        before hitting it.
        """
        if not overrides:
            return self
        return QuotaPolicy(
            limits={**self.limits, **overrides},
            overage=self.overage,
            overage_tolerance_percent=self.overage_tolerance_percent,
        )


def limits_to_wire(limits: dict[QuotaResource, int | None]) -> dict[str, int | None]:
    """Convert a ``QuotaResource``-keyed limits dict to string keys for the wire.

    Single conversion point for both the JWT ``lic.limits`` claim (see
    :func:`~rhesis.backend.ee.licensing.tiers.tier_to_lic_claim`) and the
    ``GET /features`` response -- both need the same enum-to-string shape.
    """
    return {str(k): v for k, v in limits.items()}


def limits_from_wire(raw: object) -> dict[QuotaResource, int | None]:
    """Parse a wire limits mapping into ``QuotaResource`` keys, skipping junk.

    The inverse of :func:`limits_to_wire`, for a limits map that arrived as
    *data at request time* -- currently the ``lic.custom_limits`` claim of a
    signed license token, carrying a bespoke deal's negotiated caps.

    Deliberately lenient where the tier-YAML parser
    (``ee.licensing.tiers._parse_limits``) is strict, and the difference is
    the source, not the shape:

    - The YAML is authored by us, read once at startup, and validated there,
      so a bad key is a deploy-time bug worth refusing to boot over.
    - A token is validated by signature, not by schema, and is read on the
      request path. Raising here would turn one malformed claim into a 500 on
      every request for that org.

    So an unknown resource name, a non-integer, a ``bool`` (which passes
    ``isinstance(v, int)``), or a negative number is dropped with a warning
    and the tier default applies to that resource instead. That fails toward
    *not* enforcing an override we could not read, which for the enterprise
    tier this exists to serve means staying unlimited -- lenient toward the
    customer, and visible in the logs, rather than blocking work at a ceiling
    nobody can explain.

    Returns a **partial** map: only the resources *raw* actually names, so it
    is safe to merge via :meth:`QuotaPolicy.with_limit_overrides`. A non-mapping
    *raw* (including ``None``) yields an empty dict.
    """
    if not isinstance(raw, dict):
        if raw is not None:
            logger.warning("Ignoring non-mapping limits claim (got %s)", type(raw).__name__)
        return {}

    parsed: dict[QuotaResource, int | None] = {}
    for key, value in raw.items():
        try:
            resource = QuotaResource(key)
        except ValueError:
            logger.warning("Ignoring unknown resource %r in limits claim", key)
            continue

        if value is None:
            parsed[resource] = None
            continue
        # bool must be rejected explicitly: it passes isinstance(v, int).
        if isinstance(value, bool) or not isinstance(value, int):
            logger.warning(
                "Ignoring non-integer limit for %r in limits claim: %r (%s)",
                key,
                value,
                type(value).__name__,
            )
            continue
        if value < 0:
            logger.warning("Ignoring negative limit for %r in limits claim: %r", key, value)
            continue
        parsed[resource] = value

    return parsed


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
        if not get_application_settings().usage_quotas_enabled:
            return QuotaPolicy(limits=dict(UNLIMITED_LIMITS))
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
    "QUOTA_RESOURCE_LABELS",
    "QuotaPolicy",
    "QuotaProvider",
    "QuotaRegistry",
    "QuotaResource",
    "QuotaResourceLike",
    "UNLIMITED_LIMITS",
    "limits_from_wire",
    "limits_to_wire",
    "resource_label",
]

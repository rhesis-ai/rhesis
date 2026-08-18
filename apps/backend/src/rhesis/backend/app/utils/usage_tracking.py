"""Process-wide sink that accrues MODEL_TOKENS for every LLM call.

Registered once at startup (see :func:`install_usage_sink`, called from the
FastAPI lifespan and from Celery worker init). From then on every model the
SDK builds -- anywhere in the process, through any code path, whether or not
that code has heard of usage accounting -- reports its token usage here.

This replaces a per-instance ``on_usage`` closure that each model
construction site had to remember to pass. That design put the same bug in
N places: three construction sites had silently skipped accrual, and the
only reason we knew is that someone went looking at the dashboard. A sink
cannot be forgotten because there is nothing to remember.

Two inputs decide what happens to an emission:

**Who pays** -- ``BaseLLM.usage_metered``, stamped by the model-resolution
layer (``user_model_utils``, and ``metrics.strategies.local`` for per-metric
judge overrides). This cannot move to the SDK or to the provider: the same
provider class is billable or not depending on where its API key came from.
An org running ``openai`` on its own key pays OpenAI directly and must not
also pay us; the deployment's default model runs on our credentials and
must. Same class, opposite answer, decided by how the model was selected.

``None`` -- nobody stamped it -- is treated as a bug, not as a third
category, and billed. That is safe because an org's own API key can only
enter through a Model row (``_fetch_and_configure_model``,
``_resolve_metric_model``) or the connection-test form
(``model_connection``), and all of those stamp; a model that reached an LLM
call unstamped is therefore running on this deployment's credentials.
``tests/backend/app/test_language_model_construction_boundary.py`` keeps it
that way, and the two Penelope construction sites (``batch/runner.py``,
``output_providers.py``) stamp across that package boundary since Penelope
cannot stamp itself. :func:`_warn_unstamped` fires once per provider/model
so a path that slips through all of that is findable rather than silent.

**Who to bill** -- the ambient organization from
:mod:`rhesis.backend.app.usage_attribution`, read at emission time rather
than captured at construction time. When nothing is bound the tokens are
real but unattributable, which is a defect in the binding, not a reason to
drop them on the floor -- so they are counted as unattributed rather than
silently discarded (:func:`_record_unattributed`).
"""

from __future__ import annotations

import logging
from typing import Optional, Set, Tuple

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services.usage import dispatch_accrual
from rhesis.backend.app.usage_attribution import current_usage_org
from rhesis.sdk.models.base import BaseLLM, TokenUsage, set_default_usage_callback

logger = logging.getLogger(__name__)

#: Log marker for usage that arrived with no organization bound. Stable and
#: greppable on purpose -- alert on a nonzero rate of this.
UNATTRIBUTED_MARKER = "usage.unattributed"

#: Log marker for a model built outside the resolution layer, so nobody
#: recorded whose credentials pay for it. One per (provider, model) so a hot
#: loop does not drown the log.
UNSTAMPED_MARKER = "usage.unstamped_model"

#: Deliberately unsynchronised. The sink runs concurrently (async requests,
#: threadpool metric judges, the Celery threads pool), so two callers can
#: race between the membership test and the add. That is fine: ``set.add`` on
#: an already-hashed tuple is atomic under the GIL, so the race cannot corrupt
#: the set or raise -- it can only produce a duplicate log line. Dedup here is
#: best-effort noise control, not correctness, and a lock on the logging path
#: would cost more than the occasional repeated warning.
_warned_unstamped: Set[Tuple[str, str]] = set()


def _model_identity(model: BaseLLM) -> Tuple[str, str]:
    return (
        getattr(model, "PROVIDER", "") or model.__class__.__name__,
        getattr(model, "model_name", "") or "",
    )


def _warn_unstamped(model: BaseLLM) -> None:
    """Flag a model nobody recorded provenance for, once per provider/model.

    Names the provider and model only. Never the key, and never anything
    derived from it.
    """
    identity = _model_identity(model)
    if identity in _warned_unstamped:
        return
    _warned_unstamped.add(identity)
    provider, model_name = identity
    logger.warning(
        "%s: %s/%s was built outside the model-resolution layer, so nobody "
        "recorded whose credentials pay for it; billing it to the org. Route "
        "the call site through rhesis.backend.app.utils.user_model_utils.",
        UNSTAMPED_MARKER,
        provider,
        model_name,
        extra={"usage_marker": UNSTAMPED_MARKER, "provider": provider, "model": model_name},
    )


def _record_unattributed(usage: TokenUsage, model: BaseLLM) -> None:
    """Count billable usage that arrived with no organization bound.

    Deliberately not written to the ``usage`` table: it has a FK to
    ``organization.id`` and an RLS policy whose ``USING`` doubles as the
    insert check, so there is no row shape for "no org", and inventing a
    sentinel org would corrupt the table everyone bills from. A log line
    with structured fields is queryable (``JsonLogFormatter`` forwards
    ``usage_marker`` and friends) without putting fiction in the ledger.
    """
    provider, model_name = _model_identity(model)
    logger.warning(
        "%s: %s tokens from %s/%s with no organization bound; not accrued. "
        "The call path did not bind usage attribution -- see "
        "rhesis.backend.app.usage_attribution.",
        UNATTRIBUTED_MARKER,
        usage["total_tokens"],
        provider,
        model_name,
        extra={
            "usage_marker": UNATTRIBUTED_MARKER,
            "provider": provider,
            "model": model_name,
            "total_tokens": usage["total_tokens"],
        },
    )


def accrue_model_tokens(usage: TokenUsage, model: BaseLLM) -> None:
    """Accrue one model call's tokens against the ambient organization.

    The SDK hands us an already-normalized :class:`TokenUsage`, so there is
    no provider dialect to parse here. :func:`dispatch_accrual` queues the
    write on a worker and never raises, which matters most on this path:
    unlike the Celery call sites, this runs during interactive requests a
    user is waiting on.
    """
    if model.usage_metered is False:
        # The org supplied its own API key, so it already pays the provider.
        return
    if model.usage_metered is None:
        # Nobody stamped it, which is a bug rather than a category, so bill it
        # and say so once. Billing (rather than skipping) is safe only because
        # an org's own key cannot reach an unstamped model: it enters via a
        # Model row or the connection-test form, and every one of those paths
        # stamps. The invariant is enforced, not assumed --
        # tests/backend/app/test_language_model_construction_boundary.py fails
        # on any new construction site, and its allowlist documents the
        # exceptions.
        #
        # Revisit if Rhesis stops offering hosted models: once every model
        # carries an org's key, "unstamped" flips from "ours" to "theirs" and
        # billing on it would charge orgs for their own spend. Skipping would
        # be the safer default then. Today nothing is enforced against these
        # numbers (limits are display-only), so the blast radius is a wrong
        # figure on a dashboard, not a blocked user.
        _warn_unstamped(model)

    organization_id = current_usage_org()
    if not organization_id:
        _record_unattributed(usage, model)
        return

    dispatch_accrual(organization_id, QuotaResource.MODEL_TOKENS, usage["total_tokens"])


def install_usage_sink() -> None:
    """Register :func:`accrue_model_tokens` as the SDK's process-wide sink.

    Idempotent, and safe to call from both the API lifespan and Celery
    worker init -- a process only ever runs one of them, but tests exercise
    both.
    """
    set_default_usage_callback(accrue_model_tokens)


def uninstall_usage_sink() -> None:
    """Remove the sink. For tests that need a process with no accounting."""
    set_default_usage_callback(None)
    _warned_unstamped.clear()


def stamp_usage_provenance(model: object, metered: Optional[bool]) -> object:
    """Record on *model* whether we pay for its tokens, and return it.

    Called by the model-resolution layer at the point it knows where the API
    key came from. Tolerates a non-model (the resolution chain can still
    hand back a bare provider string on construction failure) so callers do
    not each need an isinstance check.
    """
    if isinstance(model, BaseLLM):
        model.usage_metered = metered
    return model

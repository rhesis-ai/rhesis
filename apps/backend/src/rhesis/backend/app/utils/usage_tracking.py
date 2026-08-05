"""Token-usage accrual callback for Rhesis-hosted LLM providers.

Passed into hosted model constructors as ``on_usage=...`` (see
``rhesis.sdk.models.base.BaseLLM.on_usage``), invoked wherever a provider
parses token usage out of its own API response -- see
``PolyphemusLLM.generate``/``generate_batch`` and ``RhesisLLM.a_generate``.
This is the successor to an earlier design that wrapped the resolved model
in a proxy object overriding ``generate()``/``a_generate()``: that broke
every ``isinstance(model, BaseLLM)`` check downstream (LLM-judge metrics,
Architect's agent loop, preflight) since the proxy was not a ``BaseLLM``
subclass, and covered only two of the four call shapes a model exposes
(missed ``generate_batch``, the primary bulk test-generation path). A
constructor-supplied callback keeps the returned object a real provider
instance -- everything downstream keeps working unchanged -- and every
provider method that parses a usage dict already has a natural place to
invoke it.

Wired in two places, for two different reasons:

- ``_is_hosted_model`` in ``rhesis.backend.app.utils.user_model_utils``,
  for an explicitly-selected Model row: only ``rhesis``/``polyphemus``
  with no org-supplied key, meaning the call goes out on
  ``RHESIS_API_KEY``. Any other provider an org picks (their own
  ``vertex_ai``, ``ollama``, ``openai``, ...) is their own infrastructure,
  never wired here regardless of whether they configured a key.
- ``_resolve_default_hosted_model``, unconditionally, for the *system
  default* an org gets when it configures no model at all -- whatever a
  deployment names as its ``DEFAULT_*_MODEL`` (e.g.
  ``vertex_ai/gemini-2.5-flash`` in dev, calling the server's own
  ``GOOGLE_APPLICATION_CREDENTIALS``) is Rhesis's own infra cost for that
  deployment, by definition of being the default.
"""

from __future__ import annotations

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services.usage import dispatch_accrual
from rhesis.sdk.models.base import TokenUsage, UsageCallback


def make_usage_accrual_callback(organization_id: str) -> UsageCallback:
    """Build an ``on_usage`` callback that accrues MODEL_TOKENS for *organization_id*.

    The callback receives an already-normalized :class:`TokenUsage` -- the
    SDK resolves each provider's spelling of "prompt tokens" before calling
    back (see ``BaseLLM._emit_usage``), so there is no parsing to do here.
    :func:`dispatch_accrual` queues the write on a worker and never raises,
    which matters most on this path: unlike the Celery call sites, this
    callback fires during interactive requests a user is waiting on.
    """

    def _on_usage(usage: TokenUsage) -> None:
        dispatch_accrual(organization_id, QuotaResource.MODEL_TOKENS, usage["total_tokens"])

    return _on_usage

"""Which provider served an LLM call.

A stamped ``ai.model.provider`` is the answer whenever it is there, because a span that
names its provider knows better than a guess from the model name. That is precisely why
an integration must stamp nothing when it cannot place the call: a stamped "unknown"
looks like an answer and stops the lookup below from running.

The model-name lookup is the fallback for spans that arrive without one -- an
integration that could not place the call, raw OTLP, a framework we do not translate, or
a trace enriched before this module existed, where only the model name survives in the
cost breakdown.
"""

from functools import lru_cache
from typing import Optional

from rhesis.backend.app.constants import AISpanAttributes
from rhesis.backend.app.schemas.enrichment import UNKNOWN_PROVIDER

# LiteLLM names providers by how it routes to them, which splits names our integrations
# report as one. Left unfolded, the same provider would appear twice in the traces filter:
# once as what the SDK stamped, once as what LiteLLM derived for a span that stamped
# nothing.
#
# vertex_ai is the sharpest case -- LiteLLM calls a bare `gemini-2.0-flash` vertex_ai but
# a prefixed `gemini/gemini-2.0-flash` gemini, while the Google ADK integration stamps
# gemini for both.
_PROVIDER_ALIASES = {
    "vertex_ai": "gemini",
    "vertex_ai_beta": "gemini",
    "cohere_chat": "cohere",
    "text-completion-openai": "openai",
    "azure_text": "azure",
    # The SDK names a provider after the company, LiteLLM after how it routes there, so
    # the same company arrived under two spellings and showed as two rows in the filter.
    # A Gemini call traced through LangChain said google, through Google ADK gemini.
    "google": "gemini",
    "mistralai": "mistral",
    "aws": "bedrock",
}


def normalize_provider(provider: Optional[str]) -> Optional[str]:
    """Fold a provider name onto the spelling the rest of the product uses."""
    if not provider:
        return None
    cleaned = str(provider).strip().lower()
    if not cleaned:
        return None
    return _PROVIDER_ALIASES.get(cleaned, cleaned)


@lru_cache(maxsize=2048)
def provider_for_model(model_name: Optional[str]) -> Optional[str]:
    """Derive a provider from a model name, or ``None`` when it cannot be placed.

    ``litellm.get_llm_provider`` raises ``BadRequestError`` for any unprefixed model it
    does not recognise -- a self-hosted deployment, or one newer than the installed
    LiteLLM -- so the exception is the normal path here, not an error worth logging on
    every row of a trace list.

    Imported lazily and cached because the read path calls this once per list row, and
    ``token_totals`` is imported by routers that have no other reason to pull in LiteLLM.
    """
    if not model_name:
        return None

    import litellm

    try:
        return normalize_provider(litellm.get_llm_provider(model_name)[1])
    except Exception:
        return None


def resolve_provider(attributes: Optional[dict], model_name: Optional[str]) -> str:
    """The provider for one span: what it reported, else what its model implies.

    Never returns ``None``. An unattributable call is recorded as ``unknown`` rather than
    dropped, for the same reason an unpriced model is recorded at zero cost: its tokens
    are real and dropping it would make the trace undercount.
    """
    stamped = normalize_provider((attributes or {}).get(AISpanAttributes.MODEL_PROVIDER))
    if stamped:
        return stamped
    return provider_for_model(model_name) or UNKNOWN_PROVIDER

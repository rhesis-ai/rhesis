"""What a hosted-model call costs, for the hosted spend cap.

Prices are never written here: they come from litellm's price list, loaded at
process start and refreshed daily through Redis (``refresh_prices``). Input
size is estimated by ``rhesis.sdk.models.input_tokens``; see ``hosted_spend``
for how calls are charged.
"""

from __future__ import annotations

import functools
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set, Tuple

from rhesis.backend.app.config.settings import get_model_settings

logger = logging.getLogger(__name__)

_unpriced_warned: Set[str] = set()


def default_model_names() -> Set[str]:
    """Our default models, with and without the provider prefix, as litellm keys them."""
    settings = get_model_settings()
    names: Set[str] = set()
    for name in (settings.generation_model, settings.evaluation_model, settings.execution_model):
        if not name:
            continue
        names.add(name)
        if "/" in name:
            names.add(name.split("/", 1)[1])
    return names


def hosted_embedding_model(embedder: Any) -> Optional[str]:
    """The embedder's model name when it is this deployment's default, which we pay for.

    Embedders carry no billing stamp, so this goes by name: an org's own row for the
    same model is counted too, which errs toward over-counting.
    """
    default = get_model_settings().embedding_model
    name = getattr(embedder, "model_name", "") or ""
    if default and (name == default or default.endswith(f"/{name}")):
        return default
    return None


def cost_usd(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost of *input_tokens* and *output_tokens* on *model_name*.

    Cached-input discounts are ignored, so cached input is counted at the full
    rate: over-counting is the safe direction for a cap.
    """
    import litellm

    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model_name, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        return prompt_cost + completion_cost
    except Exception:
        rate = _fallback_rate()
        if model_name not in _unpriced_warned:
            _unpriced_warned.add(model_name)
            log = logger.error if rate == 0 else logger.warning
            log(
                "hosted_spend: litellm has no price for %s; counting its tokens at the "
                "highest output rate of our default models (%s USD/token)",
                model_name,
                rate,
            )
        return (input_tokens + output_tokens) * rate


def _fallback_rate() -> float:
    import litellm

    rates = [
        (litellm.model_cost.get(name) or {}).get("output_cost_per_token") or 0.0
        for name in default_model_names()
    ]
    return max(rates, default=0.0)


def schema_text(response_format: Any) -> str:
    """The structured-output schema as the provider receives it, for counting."""
    if response_format is None:
        return ""
    if hasattr(response_format, "model_json_schema"):
        response_format = response_format.model_json_schema()
    try:
        return json.dumps(response_format)
    except (TypeError, ValueError):
        return str(response_format)


@functools.lru_cache(maxsize=64)
def output_input_ratio(model_name: str) -> float:
    """How many input tokens one output token costs as much as; 1 when unknown.

    Cached per model; :func:`register_prices` clears it when prices change.
    """
    input_cost = cost_usd(model_name, 1_000_000, 0)
    output_cost = cost_usd(model_name, 0, 1_000_000)
    return output_cost / input_cost if input_cost > 0 else 1.0


def register_prices(entries: Dict[str, Dict[str, Any]]) -> None:
    import litellm

    if entries:
        litellm.register_model(entries)
        output_input_ratio.cache_clear()


def load_shared_prices(raw: str) -> None:
    """Register the price entries the daily job stored in Redis."""
    register_prices(json.loads(raw).get("models") or {})


def fetch_current_prices() -> Tuple[Dict[str, Dict[str, Any]], str]:
    """Our default models' entries from litellm's current price list, and the payload to share."""
    import litellm

    cost_map = litellm.get_model_cost_map(url=litellm.model_cost_map_url)
    entries = {name: cost_map[name] for name in default_model_names() if name in cost_map}
    payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "models": entries}
    return entries, json.dumps(payload)

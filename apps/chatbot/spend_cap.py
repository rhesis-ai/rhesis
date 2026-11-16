"""The chatbot's share of the platform's daily hosted-model spend cap.

The backend owns the cap (apps/backend/src/rhesis/backend/app/quota/hosted_spend.py);
this process can't import it, so the same Redis keys are used here. Every model
call the chatbot makes is on our credentials, so every LiteLLM call is counted
and, once the day's spend reaches the cap, refused. Keep the keys below in sync
with the backend module.

As in the backend, input is counted when a call starts and output when it ends,
so calls in flight are not invisible, and nothing on the call path touches the
network: a daemon thread flushes the local count and reads the day's total
every TICK_SECONDS. If Redis is unreachable, calls are allowed.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

import litellm
import redis

from rhesis.sdk.models import (
    ModelCallRefused,
    set_default_precall_check,
    set_default_usage_callback,
)
from rhesis.sdk.models.providers.litellm import LiteLLM

logger = logging.getLogger(__name__)

HOSTED_SPEND_DB = 12  # RedisDatabase.HOSTED_SPEND in the backend
KEY_PREFIX = "hosted_spend:v1"
CAP_OVERRIDE_KEY = f"{KEY_PREFIX}:cap_usd"
PRICES_KEY = f"{KEY_PREFIX}:prices"
MICRO_USD = 1_000_000
TICK_SECONDS = 2.0
PRICE_RELOAD_SECONDS = 600
DAY_KEY_TTL_SECONDS = 2 * 24 * 3600
MEDIA_PART_TOKENS = 2_000
MAX_INPUT_TOKENS = int(os.getenv("CHATBOT_MAX_INPUT_TOKENS", "32000"))

CAP_REACHED_MESSAGE = "The demo chatbot has reached its daily capacity. Please try again tomorrow."

# A caller must not pick the model or the output size: the chatbot is public and runs
# on our credentials.
MAX_OUTPUT_TOKENS = int(os.getenv("CHATBOT_MAX_OUTPUT_TOKENS", "2048"))
ALLOWED_MODELS = {
    m.strip()
    for m in os.getenv("CHATBOT_ALLOWED_MODELS", os.getenv("DEFAULT_GENERATION_MODEL", "")).split(
        ","
    )
    if m.strip()
}


def allowed_model(model: Optional[str]) -> Optional[str]:
    """*model* if callers may choose it, else None (the chatbot's default is used)."""
    if not model or model in ALLOWED_MODELS or model.startswith("rhesis/"):
        return model or None
    logger.warning("Ignoring requested model %r: not in CHATBOT_ALLOWED_MODELS", model)
    return None


def clamped_max_tokens(max_tokens: Optional[int]) -> int:
    if not max_tokens or max_tokens <= 0:
        return MAX_OUTPUT_TOKENS
    return min(max_tokens, MAX_OUTPUT_TOKENS)


class HostedModelCapReached(ModelCallRefused):
    """No status_code on purpose, so the SDK's retry doesn't retry it."""

    def __init__(self) -> None:
        super().__init__(CAP_REACHED_MESSAGE)


class InputTooLarge(ModelCallRefused):
    """One call's input is over CHATBOT_MAX_INPUT_TOKENS: retrying it won't help."""

    def __init__(self) -> None:
        super().__init__("This message is too long for the demo chatbot.")


def _budget_usd() -> Optional[float]:
    raw = os.getenv("HOSTED_MODEL_DAILY_BUDGET_USD")
    return float(raw) if raw else None


def _input_tokens(model_name: str, transcript: list) -> int:
    texts, media = [], 0
    for message in transcript:
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
            continue
        for part in content or []:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text") or ""))
            else:
                media += 1
    text = "\n".join(texts)
    if len(text) > MAX_INPUT_TOKENS * 8:
        return MAX_INPUT_TOKENS + 1
    try:
        return litellm.token_counter(model=model_name, text=text) + media * MEDIA_PART_TOKENS
    except Exception:
        return len(text) // 2 + media * MEDIA_PART_TOKENS


def _cost_usd(model_name: str, input_tokens: int, output_tokens: int) -> float:
    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model_name, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        return prompt_cost + completion_cost
    except Exception:
        # Unpriced: count it at the default model's output rate rather than not at all.
        default = os.getenv("DEFAULT_GENERATION_MODEL", "")
        rate = (litellm.model_cost.get(default) or {}).get("output_cost_per_token") or 0.0
        logger.warning("hosted_spend: litellm has no price for %s", model_name)
        return (input_tokens + output_tokens) * rate


class SpendCap:
    def __init__(self, broker_url: str) -> None:
        parts = urlsplit(broker_url)
        url = urlunsplit((parts.scheme, parts.netloc, f"/{HOSTED_SPEND_DB}", parts.query, ""))
        self._redis = redis.Redis.from_url(
            url, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5
        )
        self._pending_micro = 0.0
        self._lock = threading.Lock()
        self._capped = False
        self._total_micro = 0
        self._cap_micro: Optional[float] = None
        self._redis_ok = True
        self._prices_loaded_at: Optional[float] = None
        try:
            self._tick()
        except Exception as exc:
            logger.warning(f"hosted_spend: first read failed: {exc}")
        threading.Thread(target=self._run, name="hosted-spend", daemon=True).start()

    def check(self, model, request) -> None:
        """SDK pre-call check: refuse when capped or too large; count the input now."""
        if not isinstance(model, LiteLLM):
            return
        # The last total read plus what this process spent since: a burst here is
        # refused before the next tick shows it to everyone.
        projected = self._total_micro + self._pending_micro
        if self._capped or (self._cap_micro is not None and projected >= self._cap_micro):
            raise HostedModelCapReached()
        input_tokens = 0
        for transcript in request["messages"]:
            tokens = _input_tokens(model.model_name, transcript)
            if tokens > MAX_INPUT_TOKENS:
                raise InputTooLarge()
            input_tokens += tokens
        self._add(_cost_usd(model.model_name, input_tokens, 0))

    def record(self, usage, model) -> None:
        """SDK usage sink: count the output; the input was counted by check()."""
        if isinstance(model, LiteLLM):
            self._add(_cost_usd(model.model_name, 0, usage["output_tokens"]))

    def _add(self, usd: float) -> None:
        # Fractions of a micro-dollar are kept until the flush, or tiny calls would vanish.
        with self._lock:
            self._pending_micro += usd * MICRO_USD

    def _run(self) -> None:
        while True:
            try:
                self._tick()
                self._redis_ok = True
            except Exception as exc:
                self._capped, self._cap_micro = False, None
                if self._redis_ok:
                    logger.warning(f"hosted_spend: Redis unavailable, cap not enforced: {exc}")
                self._redis_ok = False
            time.sleep(TICK_SECONDS)

    def _tick(self) -> None:
        with self._lock:
            pending = int(self._pending_micro)
            self._pending_micro -= pending
        key = f"{KEY_PREFIX}:{datetime.now(timezone.utc).date().isoformat()}"
        try:
            pipe = self._redis.pipeline(transaction=False)
            if pending:
                pipe.incrby(key, pending)
                pipe.expire(key, DAY_KEY_TTL_SECONDS)
            pipe.mget(key, CAP_OVERRIDE_KEY)
            total_raw, override_raw = pipe.execute()[-1]
        except Exception:
            with self._lock:
                self._pending_micro += pending
            raise

        cap = float(override_raw) if override_raw is not None else _budget_usd()
        self._total_micro = int(total_raw or 0)
        self._cap_micro = None if cap is None else cap * MICRO_USD
        self._capped = cap is not None and self._total_micro >= self._cap_micro
        self._reload_prices_if_due()

    def _reload_prices_if_due(self) -> None:
        now = time.monotonic()
        loaded = self._prices_loaded_at
        if loaded is not None and now - loaded < PRICE_RELOAD_SECONDS:
            return
        self._prices_loaded_at = now
        raw = self._redis.get(PRICES_KEY)
        if raw:
            models = json.loads(raw).get("models") or {}
            if models:
                litellm.register_model(models)


def install_spend_cap() -> Optional[SpendCap]:
    """Count and cap this process's model calls, when a budget and Redis are configured."""
    broker_url = os.getenv("BROKER_URL")
    if _budget_usd() is None or not broker_url:
        return None
    cap = SpendCap(broker_url)
    set_default_usage_callback(cap.record)
    set_default_precall_check(cap.check)
    logger.info("Hosted spend cap installed")
    return cap

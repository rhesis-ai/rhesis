"""Daily caps on what hosted models cost us: for the whole platform and per org.

The per-org ``MODEL_TOKENS`` quota bounds one org's month, and is only checked
when a model is resolved, so a long run can go far past it. This module bounds
the day, on every call. Each call a hosted model makes on our credentials adds
its cost to one Redis counter per UTC day for the platform and one for the org
that made it. Once the platform counter reaches
``HOSTED_MODEL_DAILY_BUDGET_USD`` every hosted call is refused
(:class:`HostedModelCapReached`). Once an org's reaches
``HOSTED_MODEL_ORG_DAILY_BUDGET_USD`` that org's calls are refused
(:class:`HostedModelOrgCapReached`), so one account, or one huge run, can't use
up the platform's day for everyone. Orgs on their own API keys are never
counted or refused.

Input is counted when a call starts, from an estimate of its tokens, and output
when it ends. Counting everything at the end would leave calls in flight
invisible: hundreds of large prompts started together would all be paid for
before any of them showed up. A single request over
``HOSTED_MODEL_MAX_INPUT_TOKENS`` is refused outright
(:class:`HostedRequestTooLarge`).

Nothing on the call path touches the network. :meth:`HostedSpend.admit` and
:meth:`HostedSpend.record_output` add to in-process counters and read
in-process flags. A daemon thread per process does the Redis work every
``TICK_SECONDS``: it flushes the counters, reads the day's totals and the cap
overrides, and sets the flags. The cost is a cap that can overshoot by a couple
of seconds of spend per process.

Redis keys (DB ``RedisDatabase.HOSTED_SPEND``); the platform keys are shared
with ``apps/chatbot/spend_cap.py``, which can't import this package:

- ``hosted_spend:v1:{YYYY-MM-DD}``: the platform's spend that day, in micro-dollars.
- ``hosted_spend:v1:{YYYY-MM-DD}:org:{org_id}``: one org's spend that day.
- ``hosted_spend:v1:cap_usd``: a live override of the platform cap; ``0``
  refuses every hosted call. ``DEL`` it to go back to the env value.
- ``hosted_spend:v1:org_cap_usd``: a live override of the per-org cap for all orgs.
- ``hosted_spend:v1:org_cap_usd:{org_id}``: the per-org cap for one org, which
  wins over both of the above (to give a customer more, or less).
- ``hosted_spend:v1:prices``: litellm price entries for our default models,
  refreshed daily by the ``refresh_model_prices`` job.

If Redis is unreachable the caps fail open; the monthly quota still applies.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.quota import hosted_pricing
from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase
from rhesis.sdk.models.base import ModelCallRefused, ModelCallRequest

logger = logging.getLogger(__name__)

KEY_PREFIX = "hosted_spend:v1"
CAP_OVERRIDE_KEY = f"{KEY_PREFIX}:cap_usd"
ORG_CAP_OVERRIDE_KEY = f"{KEY_PREFIX}:org_cap_usd"
PRICES_KEY = f"{KEY_PREFIX}:prices"

MICRO_USD = 1_000_000
TICK_SECONDS = 2.0
PRICE_RELOAD_SECONDS = 600
DAY_KEY_TTL_SECONDS = 2 * 24 * 3600
PRICES_TTL_SECONDS = 7 * 24 * 3600
ALERT_PERCENTS = (80, 100)

#: Log markers, stable and greppable for Loki alerts.
THRESHOLD_MARKER = "hosted_spend.threshold"
CAP_REACHED_MARKER = "hosted_spend.cap_reached"
ORG_CAP_REACHED_MARKER = "hosted_spend.org_cap_reached"

CAP_REACHED_MESSAGE = (
    "The Rhesis default model has reached its daily capacity. Add your own model in "
    "Settings → Models to keep going, or try again tomorrow."
)
ORG_CAP_REACHED_MESSAGE = (
    "Your organization has used today's allowance on the Rhesis default model. Add your "
    "own model in Settings → Models to keep going, or try again tomorrow."
)


class HostedModelRefused(ModelCallRefused):
    """A hosted-model call refused by one of the spend limits.

    No ``status_code`` attribute on purpose: the SDK's ``llm_retry`` retries
    anything carrying a 5xx/429 status, and retrying a refusal only waits
    longer for the same answer. ``http_status`` is what the API answers with.
    """

    error_code = "hosted_model_refused"
    http_status = 503
    resets_daily = True


class HostedModelCapReached(HostedModelRefused):
    """The platform's daily hosted-model budget is used up."""

    error_code = "hosted_model_at_capacity"

    def __init__(self) -> None:
        super().__init__(CAP_REACHED_MESSAGE)


class HostedModelOrgCapReached(HostedModelRefused):
    """This org's daily hosted-model allowance is used up."""

    error_code = "hosted_model_org_daily_limit"

    def __init__(self) -> None:
        super().__init__(ORG_CAP_REACHED_MESSAGE)


class HostedRequestTooLarge(HostedModelRefused):
    """One request is bigger than a hosted call may be."""

    error_code = "hosted_model_request_too_large"
    http_status = 413
    resets_daily = False

    def __init__(self, tokens: int, limit: int) -> None:
        super().__init__(
            f"This request is too large for the Rhesis default model (about {tokens:,} input "
            f"tokens; the limit is {limit:,}). Shorten it, or use your own model."
        )


def day_key(day: date, org_id: Optional[str] = None) -> str:
    base = f"{KEY_PREFIX}:{day.isoformat()}"
    return f"{base}:org:{org_id}" if org_id else base


def seconds_until_reset(now: Optional[datetime] = None) -> int:
    """Seconds until the UTC day rolls over and the counters start from zero."""
    now = now or datetime.now(timezone.utc)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), timezone.utc)
    return max(1, int((tomorrow - now).total_seconds()))


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _whole(micro: float) -> tuple[int, float]:
    """Split pending micro-dollars into what to flush now and the fraction to keep."""
    whole = int(micro)
    return whole, micro - whole


def _usd_or_none(raw: Optional[str], key: str) -> Optional[float]:
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning(f"hosted_spend: ignoring unreadable {key}={raw!r}")
        return None


def _micro_or_none(usd: Optional[float]) -> Optional[float]:
    return None if usd is None else usd * MICRO_USD


def _over(total_micro: float, cap_micro: Optional[float]) -> bool:
    return cap_micro is not None and total_micro >= cap_micro


@dataclass
class _Reading:
    """One tick's view of Redis."""

    platform_micro: int
    platform_cap_usd: Optional[float]
    org_cap_default_usd: Optional[float] = None
    org_micro: Dict[str, int] = field(default_factory=dict)
    org_cap_usd: Dict[str, Optional[float]] = field(default_factory=dict)


class HostedSpend(RedisBackedCache):
    def __init__(self) -> None:
        # The monitor thread is the only Redis user, plus the daily price job.
        super().__init__(
            redis_db=RedisDatabase.HOSTED_SPEND, cache_name="hosted-spend", max_connections=2
        )
        self._lock = threading.Lock()
        self._pending_micro = 0.0
        self._pending_org: Dict[str, float] = {}
        self._active_orgs: Set[str] = set()
        self._day = _utc_today()
        self._capped = False
        self._capped_orgs: Set[str] = set()
        # The last totals and caps read, in micro-dollars, so a burst inside this process
        # is refused before the next tick shows it to everyone.
        self._platform_total = 0
        self._platform_cap: Optional[float] = None
        self._org_totals: Dict[str, int] = {}
        self._org_caps: Dict[str, Optional[float]] = {}
        self._org_cap_default: Optional[float] = None
        self._redis_ok = True
        self._monitor: Optional[threading.Thread] = None
        self._monitor_pid: Optional[int] = None
        self._monitor_lock = threading.Lock()
        self._prices_loaded_at: Optional[float] = None
        if hasattr(os, "register_at_fork"):
            os.register_at_fork(after_in_child=self._after_fork)

    def _after_fork(self) -> None:
        """A forked child (a prefork Celery worker) starts from a clean slate.

        It inherits the parent's locks, possibly held by the parent's monitor thread at
        the moment of the fork, and a Redis client it must not share.
        """
        self._lock = threading.Lock()
        self._monitor_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._monitor = None
        self._pending_micro, self._pending_org = 0.0, {}
        self._redis = self._redis_read = None
        self._initialized = False

    # ── Call path: memory only ─────────────────────────────────────────

    @staticmethod
    def enabled() -> bool:
        return get_application_settings().hosted_model_daily_budget_usd is not None

    def check_capacity(self, org_id: Optional[str]) -> None:
        """Refuse when the platform's or *org_id*'s day is used up."""
        if not self.enabled():
            return
        self._ensure_monitor()
        if self._capped or _over(self._platform_total + self._pending_micro, self._platform_cap):
            raise HostedModelCapReached()
        if not org_id:
            return
        if org_id not in self._active_orgs:
            # Seen here first (an API pod resolving a run whose spend happened in the
            # workers): the next tick reads its total.
            with self._lock:
                self._active_orgs.add(org_id)
        org_total = self._org_totals.get(org_id, 0) + self._pending_org.get(org_id, 0)
        org_cap = self._org_caps.get(org_id, self._org_cap_default)
        if org_id in self._capped_orgs or _over(org_total, org_cap):
            raise HostedModelOrgCapReached()

    def admit(self, model_name: str, request: ModelCallRequest, org_id: Optional[str]) -> None:
        """Refuse a call that may not run; otherwise count its input now."""
        if not self.enabled():
            return
        self.check_capacity(org_id)
        limit = get_application_settings().hosted_model_max_input_tokens
        # The schema is sent, and billed, with every prompt.
        schema = hosted_pricing.schema_text(request.get("response_format"))
        schema_part = [{"role": "system", "content": schema}] if schema else []
        input_tokens = 0
        for transcript in request["messages"]:
            tokens = hosted_pricing.estimate_input_tokens(model_name, [*transcript, *schema_part])
            if tokens > limit:
                raise HostedRequestTooLarge(tokens, limit)
            input_tokens += tokens
        self._add(org_id, hosted_pricing.cost_usd(model_name, input_tokens, 0))

    def record_input(self, model_name: str, text: str, org_id: Optional[str]) -> None:
        """Count the input of a call that bypasses the SDK hook (embeddings)."""
        if not self.enabled():
            return
        tokens = hosted_pricing.estimate_input_tokens(
            model_name, [{"role": "user", "content": text}]
        )
        self._add(org_id, hosted_pricing.cost_usd(model_name, tokens, 0))

    def record_output(self, model_name: str, output_tokens: int, org_id: Optional[str]) -> None:
        """Count a finished call's output; its input was counted by :meth:`admit`."""
        if not self.enabled() or output_tokens <= 0:
            return
        self._add(org_id, hosted_pricing.cost_usd(model_name, 0, output_tokens))

    def _add(self, org_id: Optional[str], usd: float) -> None:
        # Fractions of a micro-dollar are kept until the flush, or tiny calls would vanish.
        micro = usd * MICRO_USD
        if micro <= 0:
            return
        with self._lock:
            self._pending_micro += micro
            if org_id:
                self._pending_org[org_id] = self._pending_org.get(org_id, 0) + micro
                self._active_orgs.add(org_id)
        self._ensure_monitor()

    # ── Monitor thread: all the Redis work ─────────────────────────────

    def start(self) -> None:
        """Read the cap state once, then start the monitor.

        Called at process startup, off any request path. Without the first
        read, a new process allows calls until its monitor's first tick.
        """
        if not self.enabled():
            return
        try:
            self.tick()
        except Exception:
            logger.warning("hosted_spend: first read failed", exc_info=True)
        self._ensure_monitor()

    def _ensure_monitor(self) -> None:
        # A forked Celery child inherits the object but not the thread.
        pid = os.getpid()
        if self._monitor is not None and self._monitor_pid == pid and self._monitor.is_alive():
            return
        with self._monitor_lock:
            if self._monitor is not None and self._monitor_pid == pid and self._monitor.is_alive():
                return
            self._monitor = threading.Thread(target=self._run, name="hosted-spend", daemon=True)
            self._monitor_pid = pid
            self._monitor.start()

    def _run(self) -> None:
        while True:
            try:
                self.tick()
            except Exception:
                logger.warning("hosted_spend: monitor tick failed", exc_info=True)
            time.sleep(TICK_SECONDS)

    def tick(self) -> None:
        """Flush pending spend, read the day's totals and caps, set the flags."""
        self.initialize()
        client = self._redis
        if client is None:
            self._fail_open()
            return

        today = _utc_today()
        with self._lock:
            pending, self._pending_micro = _whole(self._pending_micro)
            pending_org = {}
            for org_id, micro in self._pending_org.items():
                pending_org[org_id], self._pending_org[org_id] = _whole(micro)
            if today != self._day:
                self._day, self._active_orgs = today, set(pending_org)
            orgs = sorted(self._active_orgs)
        try:
            reading = self._exchange(client, today, pending, pending_org, orgs)
        except Exception as exc:
            # Put it back: a double count after a partial write is the safe side.
            with self._lock:
                self._pending_micro += pending
                for org_id, micro in pending_org.items():
                    self._pending_org[org_id] = self._pending_org.get(org_id, 0) + micro
            self._fail_open(exc)
            return
        if not self._redis_ok:
            logger.info("hosted_spend: Redis reachable again, caps enforced")
        self._redis_ok = True
        self._apply(client, today, reading)
        self._reload_prices_if_due(client)

    def _fail_open(self, exc: Optional[Exception] = None) -> None:
        self._capped = False
        self._capped_orgs = set()
        self._platform_cap, self._org_caps, self._org_cap_default = None, {}, None
        if exc is not None and self._redis_ok:
            logger.warning(f"hosted_spend: Redis unavailable, caps not enforced: {exc}")
        self._redis_ok = exc is None and self._redis_ok

    @staticmethod
    def _exchange(
        client: Any, today: date, pending: int, pending_org: Dict[str, int], orgs: List[str]
    ) -> _Reading:
        """One round trip: add what this process spent, read what everyone spent."""
        pipe = client.pipeline(transaction=False)
        for org_id, micro in [(None, pending), *pending_org.items()]:
            if micro:
                pipe.incrby(day_key(today, org_id), micro)
                pipe.expire(day_key(today, org_id), DAY_KEY_TTL_SECONDS)
        keys = [day_key(today), CAP_OVERRIDE_KEY, ORG_CAP_OVERRIDE_KEY]
        keys += [day_key(today, org_id) for org_id in orgs]
        keys += [f"{ORG_CAP_OVERRIDE_KEY}:{org_id}" for org_id in orgs]
        pipe.mget(keys)
        values = pipe.execute()[-1]

        settings = get_application_settings()
        platform_cap = _usd_or_none(values[1], CAP_OVERRIDE_KEY)
        org_cap_all = _usd_or_none(values[2], ORG_CAP_OVERRIDE_KEY)
        if org_cap_all is None:
            org_cap_all = settings.hosted_model_org_daily_budget_usd
        reading = _Reading(
            org_cap_default_usd=org_cap_all,
            platform_micro=int(values[0] or 0),
            platform_cap_usd=(
                platform_cap if platform_cap is not None else settings.hosted_model_daily_budget_usd
            ),
        )
        totals, overrides = values[3 : 3 + len(orgs)], values[3 + len(orgs) :]
        for org_id, total, override in zip(orgs, totals, overrides, strict=True):
            own = _usd_or_none(override, f"{ORG_CAP_OVERRIDE_KEY}:{org_id}")
            reading.org_micro[org_id] = int(total or 0)
            reading.org_cap_usd[org_id] = own if own is not None else org_cap_all
        return reading

    def _apply(self, client: Any, today: date, reading: _Reading) -> None:
        cap = reading.platform_cap_usd
        self._capped = cap is not None and reading.platform_micro >= cap * MICRO_USD
        self._platform_total, self._platform_cap = reading.platform_micro, _micro_or_none(cap)
        self._org_totals = dict(reading.org_micro)
        self._org_caps = {org: _micro_or_none(c) for org, c in reading.org_cap_usd.items()}
        self._org_cap_default = _micro_or_none(reading.org_cap_default_usd)
        if cap is not None:
            self._alert_platform(client, today, reading.platform_micro, cap)

        capped_orgs = set()
        for org_id, micro in reading.org_micro.items():
            org_cap = reading.org_cap_usd.get(org_id)
            if org_cap is not None and micro >= org_cap * MICRO_USD:
                capped_orgs.add(org_id)
                self._alert_org(client, today, org_id, micro, org_cap)
        self._capped_orgs = capped_orgs

    @staticmethod
    def _alert_once(client: Any, flag: str) -> bool:
        return bool(client.set(f"{KEY_PREFIX}:alerted:{flag}", 1, nx=True, ex=DAY_KEY_TTL_SECONDS))

    def _alert_platform(self, client: Any, today: date, total_micro: int, cap_usd: float) -> None:
        """Log each platform threshold once a day across all processes."""
        spent_usd = total_micro / MICRO_USD
        for percent in ALERT_PERCENTS:
            if spent_usd < cap_usd * percent / 100:
                continue
            if not self._alert_once(client, f"{today.isoformat()}:{percent}"):
                continue
            marker = CAP_REACHED_MARKER if percent == 100 else THRESHOLD_MARKER
            logger.warning(
                "%s: hosted models have spent %.2f USD today, %d%% of the %.2f USD cap",
                marker,
                spent_usd,
                percent,
                cap_usd,
                extra={
                    "usage_marker": marker,
                    "spent_usd": round(spent_usd, 2),
                    "cap_usd": cap_usd,
                    "percent": percent,
                },
            )

    def _alert_org(
        self, client: Any, today: date, org_id: str, total_micro: int, cap_usd: float
    ) -> None:
        if not self._alert_once(client, f"{today.isoformat()}:org:{org_id}"):
            return
        spent_usd = total_micro / MICRO_USD
        logger.warning(
            "%s: organization %s has spent %.2f USD on hosted models today (cap %.2f USD)",
            ORG_CAP_REACHED_MARKER,
            org_id,
            spent_usd,
            cap_usd,
            extra={
                "usage_marker": ORG_CAP_REACHED_MARKER,
                "organization_id": org_id,
                "spent_usd": round(spent_usd, 2),
                "cap_usd": cap_usd,
            },
        )

    # ── Prices ─────────────────────────────────────────────────────────

    def _reload_prices_if_due(self, client: Any) -> None:
        now = time.monotonic()
        if (
            self._prices_loaded_at is not None
            and now - self._prices_loaded_at < PRICE_RELOAD_SECONDS
        ):
            return
        self._prices_loaded_at = now
        try:
            raw = client.get(PRICES_KEY)
        except Exception as exc:
            logger.warning(f"hosted_spend: could not read prices: {exc}")
            return
        if raw:
            hosted_pricing.load_shared_prices(raw)

    def refresh_prices(self) -> int:
        """Fetch litellm's current price list and share our models' entries via Redis.

        Run daily by the ``refresh_model_prices`` job. Returns how many entries
        were stored.
        """
        entries, payload = hosted_pricing.fetch_current_prices()
        if not entries:
            logger.warning("hosted_spend: litellm's price list has none of our default models")
            return 0
        hosted_pricing.register_prices(entries)

        self.initialize()
        if self._redis is None:
            return 0
        self._redis.set(PRICES_KEY, payload, ex=PRICES_TTL_SECONDS)
        return len(entries)


hosted_spend = HostedSpend()

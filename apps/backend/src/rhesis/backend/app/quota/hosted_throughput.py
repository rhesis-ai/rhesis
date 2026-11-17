"""Per-minute caps on hosted-model throughput, for the whole platform and per org.

The daily caps in ``hosted_spend`` bound how much a day may cost; this bounds how fast,
so a burst can't spend the day's budget in a few minutes and leave every user refused
until midnight. Throughput is counted in weighted tokens: input tokens plus output tokens
weighted by the model's output-to-input price ratio (6 for Gemini 3.1 Flash-Lite), which
is also how Vertex AI counts Provisioned Throughput.

Over a limit, a call gets :class:`HostedThroughputExceeded`: HTTP 429 with a
``Retry-After`` until the next minute. Unlike the daily caps it is transient, so the SDK
and batch runs retry it.

Each process counts locally and the ``HostedSpend`` monitor syncs with Redis every
couple of seconds (:meth:`ThroughputWindow.sync`), so the call path never touches the
network. Keys (DB ``RedisDatabase.HOSTED_SPEND``):

- ``hosted_spend:v1:tpm:{YYYYMMDDHHMM}`` and ``...:{YYYYMMDDHHMM}:org:{org_id}``: weighted
  tokens used in that UTC minute.
- ``hosted_spend:v1:tpm_limit``, ``hosted_spend:v1:org_tpm_limit`` and
  ``hosted_spend:v1:org_tpm_limit:{org_id}``: live overrides of
  ``HOSTED_MODEL_TOKENS_PER_MINUTE`` / ``HOSTED_MODEL_ORG_TOKENS_PER_MINUTE``.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.quota import hosted_pricing
from rhesis.backend.app.quota.hosted_refusals import (
    KEY_PREFIX,
    HostedThroughputExceeded,
    parse_override,
)

logger = logging.getLogger(__name__)

WINDOW_PREFIX = f"{KEY_PREFIX}:tpm"
LIMIT_OVERRIDE_KEY = f"{KEY_PREFIX}:tpm_limit"
ORG_LIMIT_OVERRIDE_KEY = f"{KEY_PREFIX}:org_tpm_limit"
WINDOW_TTL_SECONDS = 180


def _now() -> datetime:
    return datetime.now(timezone.utc)


def minute_of(now: datetime) -> str:
    return now.strftime("%Y%m%d%H%M")


def window_key(minute: str, org_id: Optional[str] = None) -> str:
    base = f"{WINDOW_PREFIX}:{minute}"
    return f"{base}:org:{org_id}" if org_id else base


def weighted_tokens(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Tokens weighted by price: output counts as many input tokens as it costs."""
    if output_tokens <= 0:
        return float(input_tokens)
    return input_tokens + output_tokens * hosted_pricing.output_input_ratio(model_name)


def _over(used: float, incoming: float, limit: Optional[float]) -> bool:
    if limit is None:
        return False
    return used >= limit or (used > 0 and used + incoming > limit)


class ThroughputWindow:
    """This process's view of the current minute's throughput.

    Counting and checking only touch memory; :meth:`sync`, called from the monitor
    thread, flushes and reads Redis. A check adds this process's unsynced tokens to the
    last totals read, so a burst inside one process is refused before the next sync.
    Unsynced tokens belong to the minute they were counted in: if that minute ends
    before they reach Redis (an outage), they are dropped rather than charged to a later
    minute, which would refuse everyone at once when Redis returns.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Clear all state (startup, and in a forked child)."""
        self._lock = threading.Lock()
        self._pending = 0.0
        self._pending_org: Dict[str, float] = {}
        self._pending_minute: Optional[str] = None
        self._orgs: Set[str] = set()
        self._minute: Optional[str] = None
        self._total = 0.0
        self._org_totals: Dict[str, float] = {}
        self._limit: Optional[float] = None
        self._org_limits: Dict[str, Optional[float]] = {}
        self._org_limit_default: Optional[float] = None

    @staticmethod
    def enabled() -> bool:
        settings = get_application_settings()
        return (
            settings.hosted_model_tokens_per_minute is not None
            or settings.hosted_model_org_tokens_per_minute is not None
        )

    # ── Call path ──────────────────────────────────────────────────────

    def check(self, org_id: Optional[str], incoming: float = 0.0) -> None:
        """Refuse a call whose *incoming* tokens would take the platform or *org_id* over
        its per-minute limit.

        A call larger than a limit on its own is still let into an empty minute, so it
        can run at all; it then fills that minute.
        """
        minute = minute_of(_now())
        read_now = self._minute == minute
        pending_now = self._pending_minute == minute
        total = (self._total if read_now else 0.0) + (self._pending if pending_now else 0.0)
        if _over(total, incoming, self._limit):
            raise HostedThroughputExceeded(org_level=False)
        if not org_id:
            return
        if org_id not in self._orgs:
            with self._lock:
                self._orgs.add(org_id)
        org_total = (self._org_totals.get(org_id, 0.0) if read_now else 0.0) + (
            self._pending_org.get(org_id, 0.0) if pending_now else 0.0
        )
        org_limit = self._org_limits.get(org_id, self._org_limit_default)
        if _over(org_total, incoming, org_limit):
            raise HostedThroughputExceeded(org_level=True)

    def add(self, org_id: Optional[str], tokens: float) -> None:
        if tokens <= 0:
            return
        minute = minute_of(_now())
        with self._lock:
            if minute != self._pending_minute:
                self._pending, self._pending_org, self._pending_minute = 0.0, {}, minute
            self._pending += tokens
            if org_id:
                self._pending_org[org_id] = self._pending_org.get(org_id, 0.0) + tokens
                self._orgs.add(org_id)

    # ── Monitor thread ─────────────────────────────────────────────────

    def sync(self, client: Any) -> None:
        """Flush this minute's tokens and read everyone's for the minute."""
        minute = minute_of(_now())
        with self._lock:
            if minute != self._pending_minute:
                self._pending, self._pending_org, self._pending_minute = 0.0, {}, minute
            pending = int(self._pending)
            self._pending -= pending
            pending_org = {org_id: int(t) for org_id, t in self._pending_org.items()}
            for org_id, tokens in pending_org.items():
                self._pending_org[org_id] -= tokens
            if minute != self._minute:
                # Only orgs active this minute are read; quiet ones drop out.
                self._orgs = {org_id for org_id, tokens in pending_org.items() if tokens}
            orgs = sorted(self._orgs)
        try:
            values = self._exchange(client, minute, pending, pending_org, orgs)
        except Exception:
            with self._lock:
                if self._pending_minute == minute:
                    self._pending += pending
                    for org_id, tokens in pending_org.items():
                        self._pending_org[org_id] = self._pending_org.get(org_id, 0.0) + tokens
            self.fail_open()
            raise
        self._apply(minute, orgs, values)

    def fail_open(self) -> None:
        self._limit, self._org_limits, self._org_limit_default = None, {}, None

    @staticmethod
    def _exchange(
        client: Any, minute: str, pending: int, pending_org: Dict[str, int], orgs: List[str]
    ) -> List[Optional[str]]:
        pipe = client.pipeline(transaction=False)
        for org_id, tokens in [(None, pending), *pending_org.items()]:
            if tokens:
                pipe.incrby(window_key(minute, org_id), tokens)
                pipe.expire(window_key(minute, org_id), WINDOW_TTL_SECONDS)
        keys = [window_key(minute), LIMIT_OVERRIDE_KEY, ORG_LIMIT_OVERRIDE_KEY]
        keys += [window_key(minute, org_id) for org_id in orgs]
        keys += [f"{ORG_LIMIT_OVERRIDE_KEY}:{org_id}" for org_id in orgs]
        pipe.mget(keys)
        return pipe.execute()[-1]

    def _apply(self, minute: str, orgs: List[str], values: List[Optional[str]]) -> None:
        settings = get_application_settings()
        limit = parse_override(values[1], LIMIT_OVERRIDE_KEY)
        if limit is None and settings.hosted_model_tokens_per_minute is not None:
            limit = float(settings.hosted_model_tokens_per_minute)
        org_default = parse_override(values[2], ORG_LIMIT_OVERRIDE_KEY)
        if org_default is None and settings.hosted_model_org_tokens_per_minute is not None:
            org_default = float(settings.hosted_model_org_tokens_per_minute)

        totals, overrides = values[3 : 3 + len(orgs)], values[3 + len(orgs) :]
        org_totals, org_limits = {}, {}
        for org_id, total, override in zip(orgs, totals, overrides, strict=True):
            own = parse_override(override, f"{ORG_LIMIT_OVERRIDE_KEY}:{org_id}")
            org_totals[org_id] = float(total or 0)
            org_limits[org_id] = own if own is not None else org_default

        self._minute, self._total = minute, float(values[0] or 0)
        self._org_totals, self._org_limits = org_totals, org_limits
        self._limit, self._org_limit_default = limit, org_default

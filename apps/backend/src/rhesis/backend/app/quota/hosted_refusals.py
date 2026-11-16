"""What the hosted-model spend and throughput limits share: the refusals they raise,
their Redis key prefix and how they read a live override.

Kept apart from ``hosted_spend`` and ``hosted_throughput`` so both can use them without
importing each other.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from rhesis.sdk.models.base import ModelCallRefused, ModelCallThrottled

logger = logging.getLogger(__name__)

#: Prefix of every hosted spend and throughput key in Redis.
KEY_PREFIX = "hosted_spend:v1"


def parse_override(raw: Optional[str], key: str) -> Optional[float]:
    """A live override read from Redis: a non-negative number, or None if unset or unreadable."""
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning(f"hosted_spend: ignoring unreadable {key}={raw!r}")
        return None


CAP_REACHED_MESSAGE = (
    "The Rhesis default model has reached its daily capacity. Add your own model in "
    "Settings → Models to keep going, or try again tomorrow."
)
THROUGHPUT_MESSAGE = (
    "The Rhesis default model is busy. Please retry in a few seconds, or add your own "
    "model in Settings → Models."
)
ORG_THROUGHPUT_MESSAGE = (
    "Your organization is sending requests to the Rhesis default model faster than "
    "allowed. Please retry in a few seconds."
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

    def retry_after_seconds(self) -> Optional[int]:
        """Seconds a client should wait before trying again, or None if it shouldn't."""
        return seconds_until_reset() if self.resets_daily else None


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


class HostedThroughputExceeded(ModelCallThrottled, HostedModelRefused):
    """The platform or an org is over its per-minute throughput limit.

    Transient, unlike the daily caps (``ModelCallThrottled``): the SDK's ``llm_retry``
    waits out :meth:`retry_after_seconds` and tries again, and batch runs may retry the
    test.
    """

    error_code = "hosted_model_throughput_limit"
    http_status = 429
    resets_daily = False

    def __init__(self, org_level: bool) -> None:
        super().__init__(ORG_THROUGHPUT_MESSAGE if org_level else THROUGHPUT_MESSAGE)

    def retry_after_seconds(self) -> Optional[int]:
        now = datetime.now(timezone.utc)
        return max(1, 60 - now.second)


def seconds_until_reset(now: Optional[datetime] = None) -> int:
    """Seconds until the UTC day rolls over and the daily counters start from zero."""
    now = now or datetime.now(timezone.utc)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), timezone.utc)
    return max(1, int((tomorrow - now).total_seconds()))

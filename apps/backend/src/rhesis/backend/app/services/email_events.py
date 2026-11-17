"""SendGrid Event Webhook: record hard bounces.

A hard bounce on an unverified account locks it right away instead of at the
end of the grace period (see ``auth/email_verification.py``). The verification
mail is the first thing we send, so a made-up address shows up here within
minutes.
"""

import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable, Optional

from sendgrid.helpers.eventwebhook import EventWebhook
from sqlalchemy.orm import Session

from rhesis.backend.app.crud.user import mark_email_bounced
from rhesis.backend.app.utils.redact import redact_email

logger = logging.getLogger(__name__)

PUBLIC_KEY_ENV = "SENDGRID_EVENT_WEBHOOK_PUBLIC_KEY"


def webhook_public_key() -> Optional[str]:
    return os.getenv(PUBLIC_KEY_ENV) or None


@lru_cache(maxsize=4)
def _parsed_key(public_key: str):
    return EventWebhook().convert_public_key_to_ecdsa(public_key)


def signature_valid(public_key: str, payload: str, signature: str, timestamp: str) -> bool:
    # No freshness window on ``timestamp``: a replayed batch only re-stamps a bounce
    # that already happened, and we don't know whether SendGrid re-signs its retries.
    try:
        key = _parsed_key(public_key)
        return bool(EventWebhook().verify_signature(payload, signature, timestamp, key))
    except Exception:
        logger.warning("SendGrid event signature check failed", exc_info=True)
        return False


def _is_hard_bounce(event: dict[str, Any]) -> bool:
    kind = event.get("event")
    if kind == "bounce":
        # "blocked" is a temporary refusal (spam filter, full mailbox), not a dead address.
        return event.get("type", "bounce") == "bounce"
    if kind == "dropped":
        # SendGrid skips addresses already on its bounce list and reports them as dropped.
        return "bounced address" in str(event.get("reason", "")).lower()
    return False


def _event_time(event: dict[str, Any]) -> datetime:
    try:
        return datetime.fromtimestamp(int(event["timestamp"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return datetime.now(timezone.utc)


def record_bounces(db: Session, events: Iterable[Any]) -> int:
    """Stamp every hard-bounced address that belongs to an account. Returns how many."""
    marked = 0
    for event in events:
        if not isinstance(event, dict) or not _is_hard_bounce(event):
            continue
        email = event.get("email")
        if not isinstance(email, str) or not email:
            continue
        if mark_email_bounced(db, email, _event_time(event)) is not None:
            marked += 1
            logger.info("Hard bounce recorded for %s", redact_email(email))
    db.commit()
    return marked

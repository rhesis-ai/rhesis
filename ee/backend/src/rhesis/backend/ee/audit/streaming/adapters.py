"""How each kind of destination receives a batch of audit events.

An adapter gets the destination's decrypted config and the events, each exactly
as ``GET /audit-events`` returns it, and raises ``DeliveryError`` when the batch
did not arrive. HTTP adapters go through ``app/utils/webhooks.post``: HTTPS,
SSRF-checked at send time, no redirects, a timeout. Any non-2xx is a failure.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import httpx

from rhesis.backend.app.utils import webhooks
from rhesis.backend.app.utils.ssrf_http_client import SSRFError

EVENTS_TYPE = "audit_log.events"
TEST_TYPE = "audit_log.test"
DATADOG_SITES = (
    "datadoghq.com",
    "us3.datadoghq.com",
    "us5.datadoghq.com",
    "datadoghq.eu",
    "ap1.datadoghq.com",
    "ap2.datadoghq.com",
    "ddog-gov.com",
)
_ERROR_BODY_CHARS = 200


class DeliveryError(Exception):
    """The batch did not reach the destination."""


@dataclass(frozen=True)
class Batch:
    organization_id: str
    destination_id: str
    events: list[dict]
    test: bool = False


def _json(value) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def _post(url: str, body: bytes, headers: dict[str, str]) -> None:
    try:
        response = webhooks.post(url, body, headers)
    except (SSRFError, httpx.HTTPError) as exc:
        raise DeliveryError(f"{type(exc).__name__}: {exc}") from exc
    if not response.is_success:
        raise DeliveryError(f"HTTP {response.status_code}: {response.text[:_ERROR_BODY_CHARS]}")


def message_id(batch: Batch) -> str:
    """The same for a retry of the same events, so a receiver can drop it by ``webhook-id``."""
    ids = "\n".join(event["id"] for event in batch.events)
    return "msg_" + hashlib.sha256(ids.encode()).hexdigest()[:32]


def send_webhook(config: dict, batch: Batch) -> None:
    body = _json(
        {
            "type": TEST_TYPE if batch.test else EVENTS_TYPE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": batch.events,
        }
    )
    _post(config["url"], body, webhooks.signed_headers(config["secret"], message_id(batch), body))


def send_splunk_hec(config: dict, batch: Batch) -> None:
    """HEC event endpoint: one JSON object per event, concatenated."""
    body = b"\n".join(
        _json(
            {
                "time": datetime.fromisoformat(event["occurred_at"]).timestamp(),
                "source": "rhesis",
                "sourcetype": "rhesis:audit",
                "event": event,
            }
        )
        for event in batch.events
    )
    headers = {"Authorization": f"Splunk {config['token']}", "content-type": "application/json"}
    _post(config["url"], body, headers)


def send_datadog(config: dict, batch: Batch) -> None:
    """Logs intake v2. ``date`` is one of Datadog's default timestamp attributes."""
    body = _json(
        [
            {
                "ddsource": "rhesis",
                "service": "rhesis-audit-log",
                "message": event["action"],
                "date": event["occurred_at"],
                "audit_event": event,
            }
            for event in batch.events
        ]
    )
    url = f"https://http-intake.logs.{config['site']}/api/v2/logs"
    _post(url, body, {"DD-API-KEY": config["api_key"], "content-type": "application/json"})


@dataclass(frozen=True)
class Kind:
    send: Callable[[dict, Batch], None]
    # Config keys shown back to admins. Everything else is a secret.
    public: tuple[str, ...]


KINDS: dict[str, Kind] = {
    "webhook": Kind(send_webhook, ("url",)),
    "splunk_hec": Kind(send_splunk_hec, ("url",)),
    "datadog": Kind(send_datadog, ("site",)),
}

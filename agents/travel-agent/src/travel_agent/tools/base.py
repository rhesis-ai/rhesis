"""Shared contract for Travel Agent tools: every call reports an outcome, none of them raise.

The agent has to keep planning when a service is down, so a tool failure is data rather
than an exception. Each tool returns a :class:`ToolOutcome`, records the failure on the
brief, and hands back a sentence the model can repeat to the user.
"""

from __future__ import annotations

import asyncio
import logging
import os
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Nominatim's usage policy requires a UA that identifies the application.
USER_AGENT = "rhesis-travel-agent/0.1 (+https://github.com/rhesis-ai/rhesis)"

REQUEST_TIMEOUT_SECONDS = 5.0
REQUEST_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.5

# Per-service (timeout, attempts). Overpass runs the query server-side and is slower and
# more variable than a plain lookup, so it gets longer to answer and only one go: retrying
# a query that was already too slow just spends the budget twice.
SERVICE_BUDGETS: dict[str, tuple[float, int]] = {
    "sights": (9.0, 1),
    "dining": (9.0, 1),
}


def budget_for(service: str) -> tuple[float, int]:
    """How long ``service`` gets per attempt, and how many attempts it is allowed."""
    return SERVICE_BUDGETS.get(service, (REQUEST_TIMEOUT_SECONDS, REQUEST_ATTEMPTS))


class ToolStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    TIMEOUT = "timeout"
    ERROR = "error"


class ToolOutcome(BaseModel):
    """What a tool call produced, including the ways it can fail."""

    status: ToolStatus
    payload: Any = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ToolStatus.OK

    @property
    def failed(self) -> bool:
        """True for timeout/error - a service problem, as opposed to a genuine empty result."""
        return self.status in (ToolStatus.TIMEOUT, ToolStatus.ERROR)


class FaultPlan(BaseModel):
    """Forced failures, so degradation paths are testable without unplugging the network."""

    faults: dict[str, ToolStatus] = Field(default_factory=dict)

    def for_service(self, service: str) -> ToolStatus | None:
        return self.faults.get(service)


def parse_faults(raw: str | None) -> FaultPlan:
    """Parse ``TRAVEL_AGENT_FAULTS`` (``weather:timeout,transit:error,sights:empty``)."""
    plan = FaultPlan()
    if not raw:
        return plan
    for entry in raw.split(","):
        service, _, status = entry.strip().partition(":")
        service = service.strip()
        if not service:
            continue
        try:
            plan.faults[service] = ToolStatus(status.strip().casefold() or "error")
        except ValueError:
            logger.warning("Ignoring unknown fault status %r for service %r", status, service)
    return plan


def active_faults() -> FaultPlan:
    """Read the fault plan from the environment on every call, so tests can vary it."""
    return parse_faults(os.environ.get("TRAVEL_AGENT_FAULTS"))


def _forced_outcome(service: str) -> ToolOutcome | None:
    status = active_faults().for_service(service)
    if status is None or status is ToolStatus.OK:
        return None
    detail = {
        ToolStatus.TIMEOUT: "request timed out",
        ToolStatus.ERROR: "service returned an error",
        ToolStatus.EMPTY: "no results",
    }[status]
    logger.info("Injecting forced %s for service %r", status.value, service)
    return ToolOutcome(status=status, detail=detail)


async def http_get_json(
    service: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> ToolOutcome:
    """GET a JSON endpoint, converting every failure mode into a :class:`ToolOutcome`.

    A fresh client per call is deliberate: the Rhesis connector runs each turn on a new
    event loop, and an ``AsyncClient`` cached across loops fails at the transport layer.
    """
    forced = _forced_outcome(service)
    if forced is not None:
        return forced

    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    last_detail = "unreachable"
    timeout_seconds, attempts = budget_for(service)

    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(url, params=params, headers=request_headers)
                response.raise_for_status()
                return ToolOutcome(status=ToolStatus.OK, payload=response.json())
        except (httpx.TimeoutException, asyncio.TimeoutError):
            last_detail = "request timed out"
            status = ToolStatus.TIMEOUT
        except httpx.HTTPStatusError as exc:
            last_detail = f"service returned HTTP {exc.response.status_code}"
            status = ToolStatus.ERROR
        except (httpx.HTTPError, ValueError) as exc:
            last_detail = f"service was unreachable ({type(exc).__name__})"
            status = ToolStatus.ERROR

        if attempt < attempts:
            logger.info("%s lookup attempt %d failed (%s); retrying", service, attempt, last_detail)
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)

    logger.warning("%s lookup failed after %d attempt(s): %s", service, attempts, last_detail)
    return ToolOutcome(status=status, detail=last_detail)


__all__ = [
    "REQUEST_ATTEMPTS",
    "REQUEST_TIMEOUT_SECONDS",
    "SERVICE_BUDGETS",
    "USER_AGENT",
    "FaultPlan",
    "ToolOutcome",
    "ToolStatus",
    "active_faults",
    "budget_for",
    "http_get_json",
    "parse_faults",
]

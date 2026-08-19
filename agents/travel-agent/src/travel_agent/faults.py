"""Last-resort guard around tool execution.

Each tool already converts its own HTTP failures into a sentence, so this middleware
exists for what they cannot anticipate: a bug that raises, or a call that hangs past the
point where the turn is still worth waiting for. Either way the agent gets a usable
string back and the turn continues.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from agent_framework import FunctionInvocationContext, FunctionMiddleware, FunctionTool
from agent_framework.exceptions import MiddlewareException

from travel_agent.brief import current_brief
from travel_agent.state import mark_unavailable

logger = logging.getLogger(__name__)

# Generous next to the tools' own 5s-per-attempt budget: this only catches a genuine hang.
TOOL_TIMEOUT_SECONDS = 20.0

# Which brief service a tool speaks for, so a hang is remembered like any other outage.
TOOL_SERVICES: dict[str, str] = {
    "resolve_destination": "places",
    "choose_candidate": "places",
    "find_sightseeing": "sights",
    "find_dining": "dining",
    "get_weather": "weather",
    "estimate_travel": "transit",
    "check_lodging_budget": "lodging",
}


class ToolFaultMiddleware(FunctionMiddleware):
    """Turn an unexpected tool crash or hang into a degraded result instead of a dead turn."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        name = context.function.name

        # Handoff tools are framework signals intercepted by MAF's own middleware; wrapping
        # them would swallow the MiddlewareTermination that actually performs the routing.
        if name.startswith("handoff_to_"):
            await call_next()
            return

        try:
            await asyncio.wait_for(call_next(), timeout=TOOL_TIMEOUT_SECONDS)
        except MiddlewareException:
            raise
        except (TimeoutError, asyncio.TimeoutError):
            context.result = self._degrade(name, "timed out")
        except Exception as exc:  # noqa: BLE001 - a tool must never break the conversation
            logger.exception("Tool %s raised; degrading the turn", name)
            context.result = self._degrade(name, f"failed unexpectedly ({type(exc).__name__})")

    @staticmethod
    def _degrade(tool_name: str, reason: str):
        service = TOOL_SERVICES.get(tool_name)
        if service:
            try:
                mark_unavailable(current_brief(), service, reason)
            except RuntimeError:
                # No bound brief: only possible outside a turn, so there is nothing to record.
                logger.warning("No trip brief bound while degrading %s", tool_name)
        return FunctionTool.parse_result(
            f"The {service or tool_name} lookup {reason}. "
            "Tell the user this detail is unavailable and continue planning without it."
        )


__all__ = ["TOOL_SERVICES", "TOOL_TIMEOUT_SECONDS", "ToolFaultMiddleware"]

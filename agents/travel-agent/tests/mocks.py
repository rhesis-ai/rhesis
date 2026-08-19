"""Test doubles: a scripted LLM and a scripted HTTP layer.

The chat client is stubbed at ``_inner_get_response``, which sits *below* MAF's function
invocation, chat middleware and telemetry layers. Everything above it - the tool loop,
the handoff middleware, the context providers, the spans - runs for real, so a script is
just the sequence of model replies one whole multi-agent turn consumes, in order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import (
    BaseChatClient,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    Message,
    ResponseStream,
)
from agent_framework._middleware import ChatMiddlewareLayer
from agent_framework._tools import FunctionInvocationLayer
from agent_framework.observability import ChatTelemetryLayer

from travel_agent.tools import base
from travel_agent.tools.base import ToolOutcome, ToolStatus


class ScriptedRawClient(BaseChatClient):
    """Innermost layer: hands back canned assistant messages and records every call."""

    def __init__(self, *, script: list[Message], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    @property
    def exhausted(self) -> bool:
        return not self._script

    def _inner_get_response(  # type: ignore[override]
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ):
        self.calls.append(
            {
                "instructions": options.get("instructions", ""),
                "tools": [getattr(t, "name", "") for t in (options.get("tools") or [])],
                "messages": list(messages),
            }
        )
        if not self._script:
            raise RuntimeError(
                f"Scripted client ran out of replies after {len(self.calls)} calls. "
                "The agent took a path the script did not cover."
            )
        message = self._script.pop(0)
        response = ChatResponse(
            messages=[message], response_id=f"scripted-{len(self.calls)}", finish_reason="stop"
        )

        if stream:

            async def _updates():
                yield ChatResponseUpdate(contents=list(message.contents), role="assistant")

            return ResponseStream(_updates(), finalizer=lambda _updates: response)

        async def _awaitable():
            return response

        return _awaitable()


class ScriptedClient(
    FunctionInvocationLayer,
    ChatMiddlewareLayer,
    ChatTelemetryLayer,
    ScriptedRawClient,
):
    """Same layer stack as ``OpenAIChatCompletionClient``, scripted at the bottom."""


def text(content: str) -> Message:
    """An assistant message that is plain text."""
    return Message(role="assistant", contents=[Content.from_text(text=content)])


def call(name: str, **arguments: Any) -> Message:
    """An assistant message that requests one tool call."""
    return Message(
        role="assistant",
        contents=[
            Content.from_function_call(call_id=f"call-{name}", name=name, arguments=arguments)
        ],
    )


def handoff(target: str) -> Message:
    """An assistant message that hands off to ``target``."""
    return call(f"handoff_to_{target}")


def back() -> Message:
    """Hand control back to the coordinator."""
    return handoff("trip_coordinator")


def client_for(*script: Message) -> ScriptedClient:
    return ScriptedClient(script=list(script))


# region scripted HTTP


class FakeHTTP:
    """Stands in for ``base.http_get_json``, keyed by service name."""

    def __init__(self, outcomes: dict[str, ToolOutcome] | None = None) -> None:
        self.outcomes = outcomes or {}
        self.requests: list[tuple[str, str]] = []

    def set(self, service: str, outcome: ToolOutcome) -> None:
        self.outcomes[service] = outcome

    async def __call__(self, service: str, url: str, **_kwargs: Any) -> ToolOutcome:
        self.requests.append((service, url))
        return self.outcomes.get(service, ToolOutcome(status=ToolStatus.OK, payload=None))

    def install(self, monkeypatch: Any) -> FakeHTTP:
        monkeypatch.setattr(base, "http_get_json", self)
        return self


def ok(payload: Any) -> ToolOutcome:
    return ToolOutcome(status=ToolStatus.OK, payload=payload)


def timeout(detail: str = "request timed out") -> ToolOutcome:
    return ToolOutcome(status=ToolStatus.TIMEOUT, detail=detail)


def error(detail: str = "service returned HTTP 503") -> ToolOutcome:
    return ToolOutcome(status=ToolStatus.ERROR, detail=detail)


# region canned payloads


def nominatim(*cities: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a Nominatim-shaped payload from ``{name, state, country, lat, lon}`` dicts."""
    return [
        {
            "addresstype": "city",
            "lat": str(city.get("lat", 0.0)),
            "lon": str(city.get("lon", 0.0)),
            "display_name": city["name"],
            "address": {
                "city": city["name"],
                "state": city.get("state"),
                "country": city.get("country"),
            },
        }
        for city in cities
    ]


def landmarks(*names: str) -> dict[str, Any]:
    """Overpass-shaped landmark payload (nodes with coordinates)."""
    return {
        "elements": [
            {"tags": {"name": name}, "lat": 35.0 + index * 0.01, "lon": 139.0 + index * 0.01}
            for index, name in enumerate(names)
        ]
    }


def overpass(*names: str) -> dict[str, Any]:
    return {"elements": [{"tags": {"name": name}} for name in names]}


def osrm(*seconds: float) -> dict[str, Any]:
    return {"durations": [[0.0, *seconds]]}


def forecast(highs: list[float], lows: list[float], codes: list[int]) -> dict[str, Any]:
    return {
        "daily": {
            "temperature_2m_max": highs,
            "temperature_2m_min": lows,
            "weather_code": codes,
        }
    }


TOKYO = {"name": "Tokyo", "country": "Japan", "lat": 35.68, "lon": 139.69}
PORTLAND_OR = {
    "name": "Portland",
    "state": "Oregon",
    "country": "United States",
    "lat": 45.5,
    "lon": -122.6,
}
PORTLAND_ME = {
    "name": "Portland",
    "state": "Maine",
    "country": "United States",
    "lat": 43.6,
    "lon": -70.2,
}


__all__ = [
    "PORTLAND_ME",
    "PORTLAND_OR",
    "TOKYO",
    "FakeHTTP",
    "ScriptedClient",
    "ScriptedRawClient",
    "back",
    "call",
    "client_for",
    "error",
    "forecast",
    "landmarks",
    "handoff",
    "nominatim",
    "ok",
    "osrm",
    "overpass",
    "text",
    "timeout",
]

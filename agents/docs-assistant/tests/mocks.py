"""A scripted model for the Agents SDK, so tests run with no provider and no key.

A script is a list of turns; each turn is the list of output items the model returns for one
request. Helpers build tool calls, text replies and answer drafts.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from typing import Any

from agents import Model
from agents.items import ModelResponse
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from docs_assistant.models import AgentModels

_ids = itertools.count(1)


def tool_call(name: str, **arguments: Any) -> ResponseFunctionToolCall:
    n = next(_ids)
    return ResponseFunctionToolCall(
        arguments=json.dumps(arguments),
        call_id=f"call_{n}",
        name=name,
        type="function_call",
        id=f"fc_{n}",
        status="completed",
    )


def text(content: str) -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id=f"msg_{next(_ids)}",
        content=[ResponseOutputText(text=content, type="output_text", annotations=[])],
        role="assistant",
        status="completed",
        type="message",
    )


def search(query: str, section: str | None = None, k: int = 6):
    return tool_call("search_docs", query=query, section=section, k=k)


def fetch(url_or_path: str, section_anchor: str | None = None):
    return tool_call("fetch_page", url_or_path=url_or_path, section_anchor=section_anchor)


def draft(**overrides: Any) -> dict[str, Any]:
    base = {
        "route": "answered",
        "answer_md": "Answer text [c1].",
        "claims": [{"text": "A claim.", "citation_ids": ["c1"]}],
        "citations": [
            {
                "id": "c1",
                "url": "https://docs.rhesis.ai/docs/metrics/metric-scope#when-to-use-multi-turn",
                "quote": "Full transcript required — context retention, multi-step threads",
            }
        ],
        "undocumented": [],
        "premise_correction": None,
        "related_pages": [],
        "clarification": None,
        "adapted_code": [],
        "conflicts": [],
    }
    return {**base, **overrides}


def submit(**overrides: Any):
    return tool_call("submit_answer", draft=draft(**overrides))


def triage_part(
    question: str,
    kind: str = "docs",
    surface: str = "unknown",
    in_scope_uncertain: bool = False,
) -> dict[str, Any]:
    return {
        "standalone_question": question,
        "kind": kind,
        "surface": surface,
        "in_scope_uncertain": in_scope_uncertain,
    }


def triage(
    *parts: dict[str, Any],
    language: str = "en",
    wants_troubleshooting: bool = False,
    clarification: dict[str, Any] | None = None,
):
    """A triage verdict as the model's JSON reply."""
    decision = {
        "parts": list(parts),
        "language": language,
        "wants_troubleshooting": wants_troubleshooting,
        "clarification": clarification,
    }
    return text(json.dumps(decision))


class ScriptedModel(Model):
    def __init__(
        self,
        script: list[list[Any]],
        *,
        tokens_per_call: int = 100,
        delay: float = 0.0,
        repeat_last: bool = False,
    ) -> None:
        self.script = list(script)
        self.tokens_per_call = tokens_per_call
        self.delay = delay
        # With repeat_last, the final turn is replayed forever (for loop and limit tests).
        self.repeat_last = repeat_last
        self.requests: list[dict[str, Any]] = []

    async def get_response(
        self,
        system_instructions,
        input,
        model_settings,
        tools,
        output_schema,
        handoffs,
        tracing,
        *,
        previous_response_id=None,
        conversation_id=None,
        prompt=None,
    ) -> ModelResponse:
        self.requests.append(
            {"system": system_instructions, "input": input, "tools": [t.name for t in tools]}
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        if not self.script:
            raise AssertionError("ScriptedModel ran out of responses")
        turn = self.script[0] if self.repeat_last and len(self.script) == 1 else self.script.pop(0)
        output = [_fresh(item) for item in turn]
        usage = Usage(
            requests=1,
            input_tokens=self.tokens_per_call,
            output_tokens=0,
            total_tokens=self.tokens_per_call,
        )
        return ModelResponse(output=output, usage=usage, response_id=None)

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError("the docs assistant does not stream model output")

    def input_text(self, request: int) -> str:
        """Everything the model was sent in one request, for asserting on tool results."""
        return json.dumps(self.requests[request]["input"], default=str)


class EchoTriage(ScriptedModel):
    """Triage that sends every message to the answer agent as one docs part."""

    def __init__(self, language: str = "en") -> None:
        super().__init__([])
        self.language = language

    async def get_response(self, system_instructions, input, *args, **kwargs) -> ModelResponse:
        question = input if isinstance(input, str) else str(input[-1].get("content"))
        self.script = [[triage(triage_part(question), language=self.language)]]
        return await super().get_response(system_instructions, input, *args, **kwargs)


def models(
    answer: Model | None = None, triage: Model | None = None, critic: Model | None = None
) -> AgentModels:
    return AgentModels(
        triage=triage or EchoTriage(), answer=answer or ScriptedModel([]), critic=critic
    )


def verdict(*supported: bool, route_ok: bool = True, reason: str = "not in the text"):
    """A critic verdict as the model's JSON reply, one flag per claim."""
    claims = [
        {"index": n, "supported": ok, "reason": "" if ok else reason}
        for n, ok in enumerate(supported, start=1)
    ]
    return text(json.dumps({"claims": claims, "route_ok": route_ok}))


def _fresh(item):
    # Replayed tool calls need new ids, or the SDK treats them as the same call.
    if isinstance(item, ResponseFunctionToolCall) and item.call_id:
        n = next(_ids)
        return item.model_copy(update={"call_id": f"call_{n}", "id": f"fc_{n}"})
    return item

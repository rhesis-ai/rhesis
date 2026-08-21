"""Golden tests for what actually reaches the exporter.

Real pipelines and real agents, driven by scripted generators so nothing touches the network. These
are the tests that would catch a span the backend rejects or an attribute the UI needs and never
gets.
"""

import asyncio
from typing import Optional

import pytest

pytest.importorskip("haystack")

from haystack import Pipeline, component  # noqa: E402
from haystack.components.agents import Agent  # noqa: E402
from haystack.components.builders import ChatPromptBuilder  # noqa: E402
from haystack.dataclasses import ChatMessage, ToolCall  # noqa: E402
from haystack.tools import Tool  # noqa: E402
from rhesis.telemetry.attributes import AIAttributes, validate_span_name  # noqa: E402
from rhesis.telemetry.constants import ConversationContext  # noqa: E402

from rhesis.sdk.telemetry.integrations.haystack.tracer import (
    rhesis_invocation_context,  # noqa: E402
)

CONV = ConversationContext.SpanAttributes

# Every attribute this integration promises to promote. Parametrized below so a rename shows up as a
# failing test rather than a quietly missing attribute in the UI.
PROMOTED_ATTRIBUTE_KEYS = frozenset(
    {
        AIAttributes.OPERATION_TYPE,
        AIAttributes.MODEL_NAME,
        AIAttributes.LLM_TOKENS_INPUT,
        AIAttributes.LLM_TOKENS_OUTPUT,
        AIAttributes.LLM_TOKENS_TOTAL,
        AIAttributes.TOOL_NAME,
        AIAttributes.TOOL_TYPE,
        AIAttributes.AGENT_NAME,
        CONV.CONVERSATION_INPUT,
        CONV.CONVERSATION_OUTPUT,
        CONV.IS_TURN_ROOT,
    }
)


@component
class ScriptedChatGenerator:
    """A ChatGenerator that returns canned replies, optionally requesting tool calls first."""

    def __init__(self, replies=None):
        self._replies = list(replies or [])
        self._calls = 0

    @component.output_types(replies=list[ChatMessage])
    def run(self, messages: list[ChatMessage], tools: Optional[list] = None, **kwargs):
        if self._calls < len(self._replies):
            reply = self._replies[self._calls]
        else:
            reply = ChatMessage.from_assistant(
                "done",
                meta={
                    "model": "scripted-1",
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 3,
                        "total_tokens": 13,
                    },
                },
            )
        self._calls += 1
        return {"replies": [reply]}

    @component.output_types(replies=list[ChatMessage])
    async def run_async(self, messages: list[ChatMessage], tools: Optional[list] = None, **kwargs):
        return self.run(messages, tools=tools, **kwargs)


def chat_pipeline(generator=None):
    pipe = Pipeline()
    pipe.add_component(
        "prompt",
        ChatPromptBuilder(template=[ChatMessage.from_user("{{q}}")], required_variables=["q"]),
    )
    pipe.add_component("llm", generator or ScriptedChatGenerator())
    pipe.connect("prompt.prompt", "llm.messages")
    return pipe


def spans_by_name(exporter):
    return {span.name: span for span in exporter.get_finished_spans()}


class TestPipelineSpans:
    def test_span_names_are_backend_valid(self, traced_exporter):
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        names = [span.name for span in exporter.get_finished_spans()]
        assert names, "expected spans"
        for name in names:
            assert validate_span_name(name), name

    def test_expected_span_tree(self, traced_exporter):
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        names = set(spans_by_name(exporter))
        assert "function.haystack.pipeline.run" in names
        assert "function.haystack.prompt" in names
        assert "ai.llm.invoke" in names

    def test_span_names_are_strings_not_enum_reprs(self, traced_exporter):
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        for span in exporter.get_finished_spans():
            assert not span.name.startswith("AIOperationType")

    def test_llm_span_carries_model_and_tokens(self, traced_exporter):
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        llm = spans_by_name(exporter)["ai.llm.invoke"]
        assert llm.attributes[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_LLM_INVOKE
        assert llm.attributes[AIAttributes.MODEL_NAME] == "scripted-1"
        assert llm.attributes[AIAttributes.LLM_TOKENS_INPUT] == 10
        assert llm.attributes[AIAttributes.LLM_TOKENS_OUTPUT] == 3
        assert llm.attributes[AIAttributes.LLM_TOKENS_TOTAL] == 13

    def test_llm_span_has_prompt_and_completion_events(self, traced_exporter):
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        llm = spans_by_name(exporter)["ai.llm.invoke"]
        event_names = [event.name for event in llm.events]
        assert "ai.prompt" in event_names
        assert "ai.completion" in event_names
        prompt = next(e for e in llm.events if e.name == "ai.prompt")
        assert prompt.attributes[AIAttributes.PROMPT_ROLE] == "user"
        assert prompt.attributes[AIAttributes.PROMPT_CONTENT] == "hello"
        completion = next(e for e in llm.events if e.name == "ai.completion")
        assert completion.attributes[AIAttributes.COMPLETION_CONTENT] == "done"

    def test_root_records_the_reply(self, traced_exporter):
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        root = spans_by_name(exporter)["function.haystack.pipeline.run"]
        assert root.attributes[CONV.CONVERSATION_OUTPUT] == "done"

    def test_no_turn_root_flag_without_a_session_id(self, traced_exporter):
        """Conversation grouping is keyed on a session, so the flag needs one to mean anything."""
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        for span in exporter.get_finished_spans():
            assert CONV.IS_TURN_ROOT not in span.attributes

    def test_turn_root_flag_appears_once_a_session_is_given(self, traced_exporter):
        exporter, _ = traced_exporter
        with rhesis_invocation_context({"session_id": "s-1"}):
            chat_pipeline().run({"prompt": {"q": "hello"}})
        root = spans_by_name(exporter)["function.haystack.pipeline.run"]
        assert root.attributes[CONV.IS_TURN_ROOT] is True

    def test_children_parent_to_the_root(self, traced_exporter):
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        spans = spans_by_name(exporter)
        root = spans["function.haystack.pipeline.run"]
        for name in ("function.haystack.prompt", "ai.llm.invoke"):
            child = spans[name]
            assert child.parent.span_id == root.context.span_id
            assert child.context.trace_id == root.context.trace_id

    def test_exactly_one_root(self, traced_exporter):
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "hello"}})
        roots = [s for s in exporter.get_finished_spans() if s.parent is None]
        assert len(roots) == 1

    def test_two_runs_produce_two_traces(self, traced_exporter):
        exporter, _ = traced_exporter
        pipe = chat_pipeline()
        pipe.run({"prompt": {"q": "one"}})
        pipe.run({"prompt": {"q": "two"}})
        roots = [s for s in exporter.get_finished_spans() if s.parent is None]
        assert len({r.context.trace_id for r in roots}) == 2

    @pytest.mark.parametrize("attribute", sorted(PROMOTED_ATTRIBUTE_KEYS))
    def test_promoted_attributes_stay_in_the_rhesis_namespaces(self, attribute):
        assert attribute.startswith(("ai.", "rhesis.")), attribute


class TestInvocationContext:
    def test_context_reaches_every_span_but_turn_root_only_the_root(self, traced_exporter):
        exporter, _ = traced_exporter
        with rhesis_invocation_context({"session_id": "s-42", "user_id": "u-7"}):
            chat_pipeline().run({"prompt": {"q": "hello"}})

        spans = exporter.get_finished_spans()
        assert len(spans) >= 3
        for span in spans:
            assert span.attributes[CONV.CONVERSATION_ID] == "s-42"
            assert span.attributes[AIAttributes.SESSION_ID] == "s-42"
            assert span.attributes["haystack.invocation.user_id"] == "u-7"

        with_flag = [s for s in spans if s.attributes.get(CONV.IS_TURN_ROOT)]
        assert len(with_flag) == 1
        assert with_flag[0].name == "function.haystack.pipeline.run"

    def test_context_does_not_leak_into_the_next_run(self, traced_exporter):
        exporter, _ = traced_exporter
        pipe = chat_pipeline()
        with rhesis_invocation_context({"session_id": "first"}):
            pipe.run({"prompt": {"q": "one"}})
        exporter.clear()
        pipe.run({"prompt": {"q": "two"}})
        for span in exporter.get_finished_spans():
            assert CONV.CONVERSATION_ID not in span.attributes

    def test_content_opt_out_keeps_the_message_off_conversation_attributes(
        self, traced_exporter, monkeypatch
    ):
        monkeypatch.setenv("RHESIS_DISABLE_CONTENT_CAPTURE", "true")
        exporter, _ = traced_exporter
        chat_pipeline().run({"prompt": {"q": "secret question"}})
        for span in exporter.get_finished_spans():
            assert CONV.CONVERSATION_INPUT not in span.attributes
            assert CONV.CONVERSATION_OUTPUT not in span.attributes


class TestAsyncPipeline:
    """Async support comes purely from ContextVars -- the tracer has no async methods.

    Haystack 2.x exposed a separate ``AsyncPipeline``; 3.0 folded it into
    ``Pipeline.run_async``. The test adapts rather than pinning one shape.
    """

    @staticmethod
    def _async_pipeline():
        try:
            from haystack import AsyncPipeline

            pipe = AsyncPipeline()
        except ImportError:
            pipe = Pipeline()
        pipe.add_component(
            "prompt",
            ChatPromptBuilder(template=[ChatMessage.from_user("{{q}}")], required_variables=["q"]),
        )
        pipe.add_component("llm", ScriptedChatGenerator())
        pipe.connect("prompt.prompt", "llm.messages")
        return pipe

    def test_async_run_produces_one_root_with_children(self, traced_exporter):
        exporter, _ = traced_exporter
        pipe = self._async_pipeline()
        if not hasattr(pipe, "run_async"):
            pytest.skip("this Haystack build has no async pipeline entry point")

        with rhesis_invocation_context({"session_id": "async-1"}):
            asyncio.run(pipe.run_async({"prompt": {"q": "hello"}}))

        spans = exporter.get_finished_spans()
        roots = [s for s in spans if s.parent is None]
        assert len(roots) == 1
        assert roots[0].name in (
            "function.haystack.async_pipeline.run",
            "function.haystack.pipeline.run",
        )
        assert roots[0].attributes[CONV.IS_TURN_ROOT] is True
        for name in [s.name for s in spans]:
            assert validate_span_name(name), name


def weather_tool():
    return Tool(
        name="get_weather",
        description="Get the weather for a city",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        function=lambda city: f"It is 18C in {city}.",
    )


class TestAgentSpans:
    def _agent(self):
        tool_call = ChatMessage.from_assistant(
            tool_calls=[ToolCall(id="c1", tool_name="get_weather", arguments={"city": "Berlin"})]
        )
        final = ChatMessage.from_assistant(
            "It is 18C in Berlin.",
            meta={"model": "scripted-1", "usage": {"prompt_tokens": 8, "completion_tokens": 5}},
        )
        return Agent(
            chat_generator=ScriptedChatGenerator(replies=[tool_call, final]),
            tools=[weather_tool()],
        )

    def test_standalone_agent_is_the_trace_root(self, traced_exporter):
        exporter, _ = traced_exporter
        agent = self._agent()
        agent.warm_up()
        agent.run(messages=[ChatMessage.from_user("weather in Berlin?")])

        spans = exporter.get_finished_spans()
        roots = [s for s in spans if s.parent is None]
        assert len(roots) == 1
        assert roots[0].name == "ai.agent.invoke"
        assert roots[0].attributes[AIAttributes.OPERATION_TYPE] == (
            AIAttributes.OPERATION_AGENT_INVOKE
        )

    def test_agent_emits_llm_and_tool_spans(self, traced_exporter):
        exporter, _ = traced_exporter
        agent = self._agent()
        agent.warm_up()
        agent.run(messages=[ChatMessage.from_user("weather in Berlin?")])

        names = [s.name for s in exporter.get_finished_spans()]
        assert names.count("ai.llm.invoke") >= 1
        assert "ai.tool.invoke" in names

    def test_tool_span_names_the_tool(self, traced_exporter):
        exporter, _ = traced_exporter
        agent = self._agent()
        agent.warm_up()
        agent.run(messages=[ChatMessage.from_user("weather in Berlin?")])

        tool_spans = [s for s in exporter.get_finished_spans() if s.name == "ai.tool.invoke"]
        assert tool_spans
        assert tool_spans[0].attributes[AIAttributes.TOOL_NAME] == "get_weather"
        assert tool_spans[0].attributes[AIAttributes.TOOL_TYPE] == "haystack"

    def test_agent_root_claims_the_turn(self, traced_exporter):
        exporter, _ = traced_exporter
        agent = self._agent()
        agent.warm_up()
        with rhesis_invocation_context({"session_id": "agent-1"}):
            agent.run(messages=[ChatMessage.from_user("weather in Berlin?")])

        with_flag = [
            s for s in exporter.get_finished_spans() if s.attributes.get(CONV.IS_TURN_ROOT)
        ]
        assert len(with_flag) == 1
        assert with_flag[0].name == "ai.agent.invoke"

    def test_every_agent_span_name_is_valid(self, traced_exporter):
        exporter, _ = traced_exporter
        agent = self._agent()
        agent.warm_up()
        agent.run(messages=[ChatMessage.from_user("weather in Berlin?")])
        for span in exporter.get_finished_spans():
            assert validate_span_name(span.name), span.name


class TestErrorSpans:
    def test_a_failing_component_records_the_error_and_re_raises(self, traced_exporter):
        exporter, _ = traced_exporter

        @component
        class Exploding:
            @component.output_types(out=str)
            def run(self, q: str):
                raise RuntimeError("kaboom")

        pipe = Pipeline()
        pipe.add_component("boom", Exploding())

        with pytest.raises(Exception, match="kaboom"):
            pipe.run({"boom": {"q": "x"}})

        errored = [
            s for s in exporter.get_finished_spans() if AIAttributes.ERROR_TYPE in s.attributes
        ]
        assert errored
        # Haystack wraps a component failure (PipelineRuntimeError in 3.0); what matters is that
        # the span is marked failed and names the error, not which wrapper class it was.
        assert errored[0].attributes[AIAttributes.ERROR_TYPE].endswith("RuntimeError")
        assert errored[0].status.status_code.name == "ERROR"

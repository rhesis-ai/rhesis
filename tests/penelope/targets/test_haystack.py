"""Tests for HaystackTarget.

Uses fakes rather than real Haystack objects (matching the other target tests), so the suite runs
without haystack-ai installed. The two tests that need real ``ChatMessage`` objects skip when it is
absent.
"""

from typing import Any, Optional

import pytest

from rhesis.penelope.targets import HaystackTarget
from rhesis.penelope.targets.haystack import _extract_reply, _first_text, _message_text


class FakePipeline:
    """Looks like a Haystack Pipeline: has ``add_component`` and ``run(data)``."""

    def __init__(self, result: Any = None, error: Optional[Exception] = None):
        self._result = result if result is not None else {"llm": {"replies": ["hello there"]}}
        self._error = error
        self.calls: list[Any] = []

    def add_component(self, *args, **kwargs):  # marks this as a Pipeline, not an Agent
        pass

    def run(self, data, **kwargs):
        self.calls.append((data, kwargs))
        if self._error:
            raise self._error
        return self._result


class FakeAgent:
    """Looks like a Haystack Agent: has ``run(messages=...)`` and no ``add_component``."""

    def __init__(self, result: Any = None, error: Optional[Exception] = None):
        self._result = result if result is not None else {"messages": []}
        self._error = error
        self.received: list[Any] = []

    def run(self, messages=None, **kwargs):
        self.received.append(messages)
        if self._error:
            raise self._error
        return self._result


class FakeMessage:
    def __init__(self, text):
        self.text = text


class TestConfiguration:
    def test_pipeline_requires_an_input_component(self):
        with pytest.raises(ValueError, match="input_component is required"):
            HaystackTarget(FakePipeline(), "p1")

    def test_pipeline_with_input_component_is_valid(self):
        target = HaystackTarget(FakePipeline(), "p1", input_component="prompt")
        assert target.target_type == "haystack"
        assert target.target_id == "p1"

    def test_agent_needs_no_input_component(self):
        target = HaystackTarget(FakeAgent(), "a1")
        assert target.target_id == "a1"

    def test_none_pipeline_is_rejected(self):
        with pytest.raises(ValueError, match="cannot be None"):
            HaystackTarget(None, "p1", input_component="prompt")

    def test_empty_target_id_is_rejected(self):
        with pytest.raises(ValueError, match="target_id cannot be empty"):
            HaystackTarget(FakeAgent(), "")

    def test_something_without_run_is_rejected(self):
        with pytest.raises(ValueError, match="run\\(\\) method"):
            HaystackTarget(object(), "x")

    def test_default_description_names_the_wrapped_type(self):
        target = HaystackTarget(FakeAgent(), "a1")
        assert "FakeAgent" in target.description

    def test_explicit_description_wins(self):
        target = HaystackTarget(FakeAgent(), "a1", description="my bot")
        assert target.description == "my bot"

    def test_agent_detection(self):
        assert HaystackTarget(FakeAgent(), "a")._is_agent is True
        assert HaystackTarget(FakePipeline(), "p", input_component="c")._is_agent is False


class TestPipelineInvocation:
    def test_message_is_fed_to_the_named_component_and_socket(self):
        pipeline = FakePipeline()
        target = HaystackTarget(pipeline, "p1", input_component="prompt", input_key="q")
        response = target.send_message("hi there")

        assert response.success is True
        assert response.content == "hello there"
        assert pipeline.calls[0][0] == {"prompt": {"q": "hi there"}}

    def test_default_input_key_is_query(self):
        pipeline = FakePipeline()
        HaystackTarget(pipeline, "p1", input_component="retriever").send_message("x")
        assert pipeline.calls[0][0] == {"retriever": {"query": "x"}}

    def test_extra_kwargs_are_forwarded(self):
        pipeline = FakePipeline()
        target = HaystackTarget(pipeline, "p1", input_component="prompt")
        target.send_message("x", include_outputs_from={"llm"})
        assert pipeline.calls[0][1] == {"include_outputs_from": {"llm"}}

    def test_output_component_scopes_the_search(self):
        pipeline = FakePipeline(
            result={"first": {"replies": ["wrong"]}, "second": {"replies": ["right"]}}
        )
        target = HaystackTarget(pipeline, "p1", input_component="prompt", output_component="second")
        assert target.send_message("x").content == "right"

    def test_output_key_is_tried_first(self):
        pipeline = FakePipeline(result={"llm": {"replies": ["a"], "custom": ["b"]}})
        target = HaystackTarget(pipeline, "p1", input_component="prompt", output_key="custom")
        assert target.send_message("x").content == "b"

    def test_custom_reply_keys_replace_the_defaults(self):
        pipeline = FakePipeline(result={"llm": {"weird_socket": ["found"]}})
        target = HaystackTarget(
            pipeline, "p1", input_component="prompt", reply_keys=("weird_socket",)
        )
        assert target.send_message("x").content == "found"

    def test_metadata_reports_the_result_keys(self):
        pipeline = FakePipeline(result={"llm": {"replies": ["a"]}, "other": {}})
        target = HaystackTarget(pipeline, "p1", input_component="prompt")
        response = target.send_message("x")
        assert response.metadata["output_keys"] == ["llm", "other"]
        assert response.metadata["is_agent"] is False

    def test_unfindable_reply_yields_empty_content_not_a_failure(self):
        pipeline = FakePipeline(result={"writer": {"documents_written": 3}})
        target = HaystackTarget(pipeline, "p1", input_component="prompt")
        response = target.send_message("x")
        assert response.success is True
        assert response.content == ""


class TestAgentInvocation:
    def test_agent_receives_the_message_as_a_chat_message(self):
        pytest.importorskip("haystack")
        agent = FakeAgent(result={"messages": [FakeMessage("agent reply")]})
        response = HaystackTarget(agent, "a1").send_message("hello")

        assert response.success is True
        assert response.content == "agent reply"
        assert len(agent.received[0]) == 1
        assert agent.received[0][0].text == "hello"

    def test_history_is_replayed_across_turns(self):
        pytest.importorskip("haystack")
        agent = FakeAgent(result={"messages": [FakeMessage("ok")]})
        target = HaystackTarget(agent, "a1")

        target.send_message("first", conversation_id="c1")
        target.send_message("second", conversation_id="c1")

        # Second call sees: user first, assistant ok, user second.
        assert [m.text for m in agent.received[1]] == ["first", "ok", "second"]

    def test_conversations_are_independent(self):
        pytest.importorskip("haystack")
        agent = FakeAgent(result={"messages": [FakeMessage("ok")]})
        target = HaystackTarget(agent, "a1")

        target.send_message("in one", conversation_id="c1")
        target.send_message("in two", conversation_id="c2")

        assert [m.text for m in agent.received[1]] == ["in two"]

    def test_no_conversation_id_means_no_history(self):
        pytest.importorskip("haystack")
        agent = FakeAgent(result={"messages": [FakeMessage("ok")]})
        target = HaystackTarget(agent, "a1")

        target.send_message("first")
        target.send_message("second")

        assert [m.text for m in agent.received[1]] == ["second"]

    def test_clear_session_forgets_the_history(self):
        pytest.importorskip("haystack")
        agent = FakeAgent(result={"messages": [FakeMessage("ok")]})
        target = HaystackTarget(agent, "a1")

        target.send_message("first", conversation_id="c1")
        target.clear_session("c1")
        target.send_message("second", conversation_id="c1")

        assert [m.text for m in agent.received[1]] == ["second"]

    def test_metadata_marks_it_as_an_agent(self):
        pytest.importorskip("haystack")
        agent = FakeAgent(result={"messages": [FakeMessage("ok")]})
        assert HaystackTarget(agent, "a1").send_message("x").metadata["is_agent"] is True


class TestFailures:
    def test_a_raising_pipeline_is_reported_not_propagated(self):
        pipeline = FakePipeline(error=RuntimeError("pipeline exploded"))
        target = HaystackTarget(pipeline, "p1", input_component="prompt")
        response = target.send_message("x")

        assert response.success is False
        assert response.content == ""
        assert "RuntimeError" in response.error
        assert "pipeline exploded" in response.error

    def test_conversation_id_is_echoed_on_failure(self):
        pipeline = FakePipeline(error=ValueError("nope"))
        target = HaystackTarget(pipeline, "p1", input_component="prompt")
        assert target.send_message("x", conversation_id="c9").conversation_id == "c9"

    def test_files_are_refused_rather_than_dropped(self):
        target = HaystackTarget(FakePipeline(), "p1", input_component="prompt")
        response = target.send_message("x", files=[{"filename": "a.pdf"}])

        assert response.success is False
        assert "file attachments" in response.error

    def test_a_failed_turn_is_not_recorded_in_history(self):
        pytest.importorskip("haystack")
        agent = FakeAgent(error=RuntimeError("boom"))
        target = HaystackTarget(agent, "a1")
        target.send_message("first", conversation_id="c1")
        assert target._session_histories.get("c1", []) == []


class TestAsync:
    @pytest.mark.asyncio
    async def test_async_send_falls_back_to_a_thread(self):
        pipeline = FakePipeline()
        target = HaystackTarget(pipeline, "p1", input_component="prompt")
        response = await target.a_send_message("hi")
        assert response.success is True
        assert response.content == "hello there"


class TestTextExtraction:
    def test_message_text_prefers_the_text_attribute(self):
        assert _message_text(FakeMessage("abc")) == "abc"

    def test_message_text_handles_plain_strings_and_dicts(self):
        assert _message_text("plain") == "plain"
        assert _message_text({"content": "from dict"}) == "from dict"

    def test_message_text_of_none_is_empty(self):
        assert _message_text(None) == ""

    def test_first_text_takes_the_last_useful_entry(self):
        """A generator's newest reply is last, and an agent's assistant turn ends the list."""
        assert _first_text([FakeMessage("old"), FakeMessage("new")]) == "new"

    def test_first_text_skips_empty_entries(self):
        assert _first_text([FakeMessage("kept"), FakeMessage("")]) == "kept"

    def test_extract_reply_searches_nested_component_output(self):
        assert _extract_reply({"llm": {"replies": ["found"]}}, ("replies",)) == "found"

    def test_extract_reply_prefers_a_top_level_key(self):
        result = {"replies": ["top"], "llm": {"replies": ["nested"]}}
        assert _extract_reply(result, ("replies",)) == "top"

    def test_extract_reply_honours_key_order(self):
        result = {"llm": {"answers": ["second"], "replies": ["first"]}}
        assert _extract_reply(result, ("replies", "answers")) == "first"
        assert _extract_reply(result, ("answers", "replies")) == "second"

    def test_extract_reply_of_a_bare_value(self):
        assert _extract_reply("just text", ("replies",)) == "just text"

    def test_extract_reply_finds_nothing(self):
        assert _extract_reply({"writer": {"count": 1}}, ("replies",)) == ""


class TestToolDocumentation:
    def test_documents_the_kind_it_wraps(self):
        agent_doc = HaystackTarget(FakeAgent(), "a1").get_tool_documentation()
        pipeline_doc = HaystackTarget(
            FakePipeline(), "p1", input_component="prompt"
        ).get_tool_documentation()
        assert "(Agent)" in agent_doc
        assert "(Pipeline)" in pipeline_doc
        assert "conversation_id" in agent_doc


class TestAgainstRealHaystack:
    """The fakes above pin the contract; these pin it against what Haystack actually returns.

    Without these, a change to Haystack's output socket names would leave every test above green
    while the target returned empty replies in production.
    """

    @staticmethod
    def _scripted_generator():
        from haystack import component
        from haystack.dataclasses import ChatMessage

        @component
        class Scripted:
            @component.output_types(replies=list[ChatMessage])
            def run(
                self, messages: list[ChatMessage], tools: Optional[list] = None, **kwargs
            ) -> dict:
                seen = [m.text for m in messages if m.text]
                return {"replies": [ChatMessage.from_assistant(f"saw: {' | '.join(seen)}")]}

            @component.output_types(replies=list[ChatMessage])
            async def run_async(
                self, messages: list[ChatMessage], tools: Optional[list] = None, **kwargs
            ) -> dict:
                return self.run(messages, tools=tools, **kwargs)

        return Scripted()

    def test_real_pipeline_reply_is_extracted(self):
        pytest.importorskip("haystack")
        from haystack import Pipeline
        from haystack.components.builders import ChatPromptBuilder
        from haystack.dataclasses import ChatMessage

        pipe = Pipeline()
        pipe.add_component(
            "prompt",
            ChatPromptBuilder(template=[ChatMessage.from_user("{{q}}")], required_variables=["q"]),
        )
        pipe.add_component("llm", self._scripted_generator())
        pipe.connect("prompt.prompt", "llm.messages")

        target = HaystackTarget(pipe, "rag", input_component="prompt", input_key="q")
        response = target.send_message("what is haystack?")

        assert response.success is True
        assert response.content == "saw: what is haystack?"

    def test_real_agent_reply_is_extracted_and_history_replays(self):
        pytest.importorskip("haystack")
        from haystack.components.agents import Agent

        agent = Agent(chat_generator=self._scripted_generator(), tools=[])
        agent.warm_up()
        target = HaystackTarget(agent, "support")

        first = target.send_message("hello", conversation_id="c1")
        assert first.success is True
        assert first.content == "saw: hello"

        second = target.send_message("again", conversation_id="c1")
        # The agent sees the prior turn, so the history round-trip is real, not just recorded.
        assert "hello" in second.content
        assert "again" in second.content

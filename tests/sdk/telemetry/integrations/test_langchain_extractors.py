"""Tests for reading LangChain invocation data into span content.

LangChain swallows exceptions raised inside a callback, so an extractor that
trips over an unexpected shape shows up as a span that never ends rather than
as an error. These cover the shapes that differ between providers.
"""

from types import SimpleNamespace

import pytest

from rhesis.sdk.telemetry.integrations.langchain.extractors import (
    extract_agent_output,
    extract_provider,
    tool_call_names,
)


class TestToolCallNames:
    """Providers return tool calls as dicts or as objects."""

    @pytest.mark.parametrize(
        "tool_calls",
        [
            pytest.param(
                [{"name": "lookup", "args": {}, "id": "1"}],
                id="dicts-as-langchain-returns-them",
            ),
            pytest.param([SimpleNamespace(name="lookup", args={}, id="1")], id="objects"),
        ],
    )
    def test_both_shapes_are_named(self, tool_calls):
        assert tool_call_names(tool_calls) == ["lookup"]

    def test_a_call_with_no_name_is_still_reported(self):
        assert tool_call_names([{}]) == ["unknown"]
        assert tool_call_names([SimpleNamespace()]) == ["unknown"]

    def test_nothing_to_name(self):
        assert tool_call_names([]) == []
        assert tool_call_names(None) == []


class TestAgentOutput:
    """A node whose reply is only tool calls still reports what it called."""

    @pytest.mark.parametrize(
        "tool_calls",
        [
            pytest.param([{"name": "lookup", "args": {}, "id": "1"}], id="dicts"),
            pytest.param([SimpleNamespace(name="lookup", args={}, id="1")], id="objects"),
        ],
    )
    def test_tool_calls_stand_in_for_empty_content(self, tool_calls):
        message = SimpleNamespace(content="", tool_calls=tool_calls)

        output = extract_agent_output({"messages": [message]})

        assert "lookup" in output

    def test_content_wins_over_tool_calls(self):
        message = SimpleNamespace(content="the answer", tool_calls=[{"name": "lookup"}])

        assert extract_agent_output({"messages": [message]}) == "the answer"

    def test_a_direct_output_key_is_used(self):
        assert extract_agent_output({"output": "done"}) == "done"

    def test_nothing_to_report(self):
        assert extract_agent_output({}) == ""


class TestExtractProvider:
    """Who served the call, from the module path, the class name or the model name."""

    @pytest.mark.parametrize(
        ("serialized", "kwargs", "expected"),
        [
            ({"id": ["langchain_openai", "ChatOpenAI"]}, {}, "openai"),
            ({"id": ["langchain_anthropic", "ChatAnthropic"]}, {}, "anthropic"),
            ({"id": ["langchain_google_genai", "ChatGoogleGenerativeAI"]}, {}, "google"),
            ({"id": ["langchain_aws", "ChatBedrock"]}, {}, "aws"),
            ({"id": ["langchain_mistralai", "ChatMistralAI"]}, {}, "mistralai"),
            ({}, {"model": "gpt-4o"}, "openai"),
        ],
    )
    def test_it_places_the_call(self, serialized, kwargs, expected):
        assert extract_provider(serialized, kwargs) == expected

    def test_an_unplaceable_call_returns_nothing(self):
        """Not the word "unknown", which is the whole point.

        The caller only stamps a provider it was given, and the backend looks the model
        up in LiteLLM when a span carries none. Stamping "unknown" looked like an
        answer, so the backend took the stamped value and skipped the lookup, leaving
        an ordinary gpt-4 call permanently unattributed whenever its payload did not
        match one of the patterns above.
        """
        assert extract_provider({"name": "MysteryLLM"}, {}) is None
        assert extract_provider({}, {}) is None

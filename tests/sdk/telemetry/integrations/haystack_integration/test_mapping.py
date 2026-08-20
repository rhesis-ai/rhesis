"""Table tests for the Haystack-to-Rhesis semantic mapping.

Pure functions, so these need no spans, no provider and no Haystack objects.
"""

import pytest
from rhesis.telemetry.attributes import AIAttributes, validate_span_name
from rhesis.telemetry.constants import ConversationContext, TestExecutionContext
from rhesis.telemetry.schemas import AIOperationType

from rhesis.sdk.telemetry.integrations.haystack import mapping


class TestResolveSpanName:
    @pytest.mark.parametrize(
        ("operation_name", "expected"),
        [
            (mapping.PIPELINE_RUN, "function.haystack.pipeline.run"),
            (mapping.ASYNC_PIPELINE_RUN, "function.haystack.async_pipeline.run"),
            (mapping.AGENT_RUN, "ai.agent.invoke"),
        ],
    )
    def test_root_operations_are_named_by_operation_alone(self, operation_name, expected):
        assert (
            mapping.resolve_span_name(
                operation_name=operation_name,
                component_type="SomeIrrelevantComponent",
                component_name="whatever",
                is_root=True,
            )
            == expected
        )

    @pytest.mark.parametrize(
        ("component_type", "expected"),
        [
            ("OpenAIChatGenerator", "ai.llm.invoke"),
            ("OpenAIGenerator", "ai.llm.invoke"),
            ("InMemoryBM25Retriever", "ai.retrieval"),
            ("SentenceTransformersTextEmbedder", "ai.embedding.generate"),
            ("ToolInvoker", "ai.tool.invoke"),
        ],
    )
    def test_component_types_map_by_suffix(self, component_type, expected):
        assert (
            mapping.resolve_span_name(
                operation_name=mapping.COMPONENT_RUN,
                component_type=component_type,
                component_name="llm",
                is_root=False,
            )
            == expected
        )

    @pytest.mark.parametrize(
        ("operation_name", "expected"),
        [
            (mapping.AGENT_STEP_LLM, "ai.llm.invoke"),
            (mapping.AGENT_STEP_TOOL, "ai.tool.invoke"),
            (mapping.AGENT_STEP, "function.haystack.agent.step"),
        ],
    )
    def test_agent_loop_operations_match_without_component_tags(self, operation_name, expected):
        """Haystack 3.0's agent-loop spans carry no component name or type at all."""
        assert (
            mapping.resolve_span_name(
                operation_name=operation_name,
                component_type=None,
                component_name="",
                is_root=False,
            )
            == expected
        )

    def test_non_root_agent_run_still_maps_to_agent_invoke(self):
        assert (
            mapping.resolve_span_name(
                operation_name=mapping.AGENT_RUN,
                component_type=None,
                component_name="specialist",
                is_root=False,
            )
            == "ai.agent.invoke"
        )

    def test_unknown_component_falls_back_to_function_name(self):
        assert (
            mapping.resolve_span_name(
                operation_name=mapping.COMPONENT_RUN,
                component_type="ChatPromptBuilder",
                component_name="prompt builder",
                is_root=False,
            )
            == "function.haystack.prompt_builder"
        )


class TestSanitizeFunctionSpanName:
    @pytest.mark.parametrize(
        ("component_name", "expected"),
        [
            ("prompt", "function.haystack.prompt"),
            ("My Component", "function.haystack.my_component"),
            ("weird!!name??", "function.haystack.weird_name"),
            ("--leading-and-trailing--", "function.haystack.leading_and_trailing"),
            ("", "function.haystack.component"),
            ("???", "function.haystack.component"),
        ],
    )
    def test_sanitizes_to_a_valid_span_name(self, component_name, expected):
        result = mapping.sanitize_function_span_name(component_name)
        assert result == expected
        assert validate_span_name(result)


class TestResolveOperationType:
    @pytest.mark.parametrize(
        ("span_name", "expected"),
        [
            ("ai.llm.invoke", AIAttributes.OPERATION_LLM_INVOKE),
            ("ai.tool.invoke", AIAttributes.OPERATION_TOOL_INVOKE),
            ("ai.retrieval", AIAttributes.OPERATION_RETRIEVAL),
            ("ai.embedding.generate", AIAttributes.OPERATION_EMBEDDING_CREATE),
            ("ai.agent.invoke", AIAttributes.OPERATION_AGENT_INVOKE),
            ("ai.agent.handoff", AIAttributes.OPERATION_AGENT_HANDOFF),
        ],
    )
    def test_known_span_names(self, span_name, expected):
        assert mapping.resolve_operation_type(span_name) == expected

    def test_function_spans_have_no_operation_type(self):
        assert mapping.resolve_operation_type("function.haystack.pipeline.run") is None


class TestMapInvocationContext:
    def test_known_keys_map_to_rhesis_attributes(self):
        attrs = mapping.map_invocation_context(
            {
                "session_id": "sess-1",
                "test_run_id": "run-1",
                "test_id": "test-1",
                "test_result_id": "result-1",
                "test_configuration_id": "config-1",
            }
        )
        assert attrs[ConversationContext.SpanAttributes.CONVERSATION_ID] == "sess-1"
        assert attrs[TestExecutionContext.SpanAttributes.TEST_RUN_ID] == "run-1"
        assert attrs[TestExecutionContext.SpanAttributes.TEST_ID] == "test-1"
        assert attrs[TestExecutionContext.SpanAttributes.TEST_RESULT_ID] == "result-1"
        assert attrs[TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID] == "config-1"

    def test_session_id_also_sets_session_and_turn_root(self):
        attrs = mapping.map_invocation_context({"session_id": "sess-1"})
        assert attrs[AIAttributes.SESSION_ID] == "sess-1"
        assert attrs[ConversationContext.SpanAttributes.IS_TURN_ROOT] is True

    def test_conversation_id_is_accepted_as_the_session(self):
        attrs = mapping.map_invocation_context({"conversation_id": "conv-9"})
        assert attrs[ConversationContext.SpanAttributes.CONVERSATION_ID] == "conv-9"
        assert attrs[AIAttributes.SESSION_ID] == "conv-9"

    def test_unknown_keys_pass_through_namespaced(self):
        attrs = mapping.map_invocation_context({"user_id": "u1", "tags": ["a", "b"]})
        assert attrs["haystack.invocation.user_id"] == "u1"
        assert attrs["haystack.invocation.tags"] == ["a", "b"]

    def test_none_values_are_dropped(self):
        assert mapping.map_invocation_context({"session_id": None, "user_id": None}) == {}

    def test_mapped_identifiers_are_stringified(self):
        """The exporter validates a whole batch at once, so one bad type sinks every span in it."""
        attrs = mapping.map_invocation_context({"session_id": 42, "test_run_id": 7})
        assert attrs[ConversationContext.SpanAttributes.CONVERSATION_ID] == "42"
        assert attrs[TestExecutionContext.SpanAttributes.TEST_RUN_ID] == "7"
        assert attrs[AIAttributes.SESSION_ID] == "42"

    def test_empty_context_maps_to_nothing(self):
        assert mapping.map_invocation_context({}) == {}


class TestSpanNameTables:
    def test_tables_hold_strings_not_enum_reprs(self):
        """``AIOperationType`` is a ``(str, Enum)``: a member formats as its repr, not its value."""
        for span_name in mapping.ROOT_SPAN_NAMES.values():
            assert isinstance(span_name, str)
            assert not span_name.startswith("AIOperationType")
        for _, _, span_name in mapping.SPAN_KIND_RULES:
            assert isinstance(span_name, str)
            assert not span_name.startswith("AIOperationType")

    def test_every_mapped_span_name_is_backend_valid(self):
        """A name the backend rejects is dropped silently, so this is the check that matters."""
        names = set(mapping.ROOT_SPAN_NAMES.values())
        names |= {span_name for _, _, span_name in mapping.SPAN_KIND_RULES}
        names.add(mapping.AGENT_STEP_SPAN_NAME)
        names.add(AIOperationType.AGENT_HANDOFF.value)
        for name in names:
            assert validate_span_name(name), name

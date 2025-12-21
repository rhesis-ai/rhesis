"""Tests for semantic layer constants."""

from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.sdk.telemetry.schemas import FORBIDDEN_SPAN_DOMAINS, AIOperationType


class TestAIOperationTypeConstants:
    """Test AIOperationType enum constants."""

    def test_llm_invoke_constant(self):
        """Test LLM_INVOKE constant value."""
        assert AIOperationType.LLM_INVOKE == "ai.llm.invoke"

    def test_tool_invoke_constant(self):
        """Test TOOL_INVOKE constant value."""
        assert AIOperationType.TOOL_INVOKE == "ai.tool.invoke"

    def test_retrieval_constant(self):
        """Test RETRIEVAL constant value."""
        assert AIOperationType.RETRIEVAL == "ai.retrieval"

    def test_embedding_generate_constant(self):
        """Test EMBEDDING_GENERATE constant value."""
        assert AIOperationType.EMBEDDING_GENERATE == "ai.embedding.generate"

    def test_all_constants_follow_pattern(self):
        """Test all AIOperationType constants follow ai.<domain>.<action> pattern."""
        import re

        pattern = r"^ai\.[a-z_]+(\.[a-z_]+)?$"
        for operation_type in AIOperationType:
            assert re.match(pattern, operation_type.value), (
                f"AIOperationType.{operation_type.name} = '{operation_type.value}' "
                f"doesn't follow pattern 'ai.<domain>.<action>'"
            )


class TestForbiddenSpanDomains:
    """Test FORBIDDEN_SPAN_DOMAINS constant."""

    def test_forbidden_domains_is_list(self):
        """Test FORBIDDEN_SPAN_DOMAINS is a list."""
        assert isinstance(FORBIDDEN_SPAN_DOMAINS, list)

    def test_forbidden_domains_contains_expected_values(self):
        """Test FORBIDDEN_SPAN_DOMAINS contains framework concepts."""
        expected_forbidden = ["agent", "chain", "workflow", "pipeline"]
        for domain in expected_forbidden:
            assert domain in FORBIDDEN_SPAN_DOMAINS, (
                f"'{domain}' should be in FORBIDDEN_SPAN_DOMAINS"
            )

    def test_forbidden_domains_are_lowercase(self):
        """Test all forbidden domains are lowercase."""
        for domain in FORBIDDEN_SPAN_DOMAINS:
            assert domain == domain.lower(), f"Domain '{domain}' should be lowercase"

    def test_forbidden_domains_no_duplicates(self):
        """Test FORBIDDEN_SPAN_DOMAINS has no duplicates."""
        assert len(FORBIDDEN_SPAN_DOMAINS) == len(set(FORBIDDEN_SPAN_DOMAINS)), (
            "FORBIDDEN_SPAN_DOMAINS should not contain duplicates"
        )


class TestAIAttributesConstants:
    """Test AIAttributes class constants."""

    def test_operation_type_attribute(self):
        """Test OPERATION_TYPE attribute key."""
        assert AIAttributes.OPERATION_TYPE == "ai.operation.type"

    def test_operation_value_constants(self):
        """Test operation type value constants."""
        assert AIAttributes.OPERATION_LLM_INVOKE == "llm.invoke"
        assert AIAttributes.OPERATION_TOOL_INVOKE == "tool.invoke"
        assert AIAttributes.OPERATION_RETRIEVAL == "retrieval"
        assert AIAttributes.OPERATION_EMBEDDING_CREATE == "embedding.create"

    def test_model_attributes(self):
        """Test model-related attribute keys."""
        assert AIAttributes.MODEL_PROVIDER == "ai.model.provider"
        assert AIAttributes.MODEL_NAME == "ai.model.name"

    def test_llm_attributes(self):
        """Test LLM-specific attribute keys."""
        assert AIAttributes.LLM_TOKENS_INPUT == "ai.llm.tokens.input"
        assert AIAttributes.LLM_TOKENS_OUTPUT == "ai.llm.tokens.output"
        assert AIAttributes.LLM_TOKENS_TOTAL == "ai.llm.tokens.total"
        assert AIAttributes.LLM_TEMPERATURE == "ai.llm.temperature"

    def test_tool_attributes(self):
        """Test tool-specific attribute keys."""
        assert AIAttributes.TOOL_NAME == "ai.tool.name"
        assert AIAttributes.TOOL_TYPE == "ai.tool.type"

    def test_event_attribute_keys(self):
        """Test event attribute keys."""
        assert AIAttributes.PROMPT_ROLE == "ai.prompt.role"
        assert AIAttributes.PROMPT_CONTENT == "ai.prompt.content"
        assert AIAttributes.COMPLETION_CONTENT == "ai.completion.content"
        assert AIAttributes.TOOL_INPUT_CONTENT == "ai.tool.input"
        assert AIAttributes.TOOL_OUTPUT_CONTENT == "ai.tool.output"

    def test_all_attributes_follow_pattern(self):
        """Test all attribute keys follow ai.* pattern."""
        import re

        # Get all string attributes from AIAttributes class
        pattern = r"^ai\.[a-z_]+(\.[a-z_]+)*$"
        for attr_name in dir(AIAttributes):
            # Skip private/dunder methods and non-string constants
            if attr_name.startswith("_"):
                continue

            attr_value = getattr(AIAttributes, attr_name)
            if isinstance(attr_value, str) and attr_value.startswith("ai."):
                assert re.match(pattern, attr_value), (
                    f"AIAttributes.{attr_name} = '{attr_value}' "
                    f"doesn't follow pattern 'ai.<component>*'"
                )


class TestAIEventsConstants:
    """Test AIEvents class constants."""

    def test_prompt_event(self):
        """Test PROMPT event name."""
        assert AIEvents.PROMPT == "ai.prompt"

    def test_completion_event(self):
        """Test COMPLETION event name."""
        assert AIEvents.COMPLETION == "ai.completion"

    def test_tool_events(self):
        """Test tool-related event names."""
        assert AIEvents.TOOL_INPUT == "ai.tool.input"
        assert AIEvents.TOOL_OUTPUT == "ai.tool.output"

    def test_retrieval_events(self):
        """Test retrieval-related event names."""
        assert AIEvents.RETRIEVAL_QUERY == "ai.retrieval.query"
        assert AIEvents.RETRIEVAL_RESULTS == "ai.retrieval.results"

    def test_all_events_follow_pattern(self):
        """Test all event names follow ai.* pattern."""
        import re

        pattern = r"^ai\.[a-z_]+(\.[a-z_]+)*$"
        for event_name in dir(AIEvents):
            # Skip private/dunder methods
            if event_name.startswith("_"):
                continue

            event_value = getattr(AIEvents, event_name)
            if isinstance(event_value, str):
                assert re.match(pattern, event_value), (
                    f"AIEvents.{event_name} = '{event_value}' "
                    f"doesn't follow pattern 'ai.<component>*'"
                )


class TestConstantConsistency:
    """Test consistency between constants and their usage."""

    def test_operation_type_values_match_span_names(self):
        """Test operation type values are related to span names."""
        # Operation type values should be suffixes of span names
        assert AIAttributes.OPERATION_LLM_INVOKE in AIOperationType.LLM_INVOKE
        assert AIAttributes.OPERATION_TOOL_INVOKE in AIOperationType.TOOL_INVOKE

    def test_no_hardcoded_strings_in_documentation(self):
        """Test that constants exist for documented patterns."""
        # This is a meta-test to ensure we're using constants
        # Check that common patterns have constants

        # Common span names should exist
        span_names = [
            AIOperationType.LLM_INVOKE,
            AIOperationType.TOOL_INVOKE,
            AIOperationType.RETRIEVAL,
        ]
        assert all(span_names), "Core span name constants should exist"

        # Common attributes should exist
        attributes = [
            AIAttributes.MODEL_NAME,
            AIAttributes.MODEL_PROVIDER,
            AIAttributes.LLM_TOKENS_INPUT,
        ]
        assert all(attributes), "Core attribute constants should exist"

        # Common events should exist
        events = [AIEvents.PROMPT, AIEvents.COMPLETION]
        assert all(events), "Core event constants should exist"

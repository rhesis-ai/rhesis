"""Tests for telemetry semantic convention helpers."""

from rhesis.sdk.telemetry.attributes import (
    AIAttributes,
    AIEvents,
    create_llm_attributes,
    create_tool_attributes,
    validate_span_name,
)


class TestAIAttributes:
    """Tests for AIAttributes class."""

    def test_ai_attributes_constants(self):
        """Test AI attribute constants are defined."""
        assert AIAttributes.SYSTEM == "ai.system"
        assert AIAttributes.REQUEST_ID == "ai.request.id"
        assert AIAttributes.OPERATION_TYPE == "ai.operation.type"
        assert AIAttributes.MODEL_PROVIDER == "ai.model.provider"
        assert AIAttributes.MODEL_NAME == "ai.model.name"
        assert AIAttributes.LLM_TOKENS_INPUT == "ai.llm.tokens.input"
        assert AIAttributes.LLM_TOKENS_OUTPUT == "ai.llm.tokens.output"
        assert AIAttributes.TOOL_NAME == "ai.tool.name"
        assert AIAttributes.TOOL_TYPE == "ai.tool.type"

        # New attributes for additional operation types
        assert AIAttributes.RERANK_MODEL == "ai.rerank.model"
        assert AIAttributes.RERANK_TOP_N == "ai.rerank.top_n"
        assert AIAttributes.EVALUATION_METRIC == "ai.evaluation.metric"
        assert AIAttributes.EVALUATION_EVALUATOR == "ai.evaluation.evaluator"
        assert AIAttributes.GUARDRAIL_TYPE == "ai.guardrail.type"
        assert AIAttributes.GUARDRAIL_PROVIDER == "ai.guardrail.provider"
        assert AIAttributes.TRANSFORM_TYPE == "ai.transform.type"
        assert AIAttributes.TRANSFORM_OPERATION == "ai.transform.operation"


class TestAIEvents:
    """Tests for AIEvents class."""

    def test_ai_events_constants(self):
        """Test AI event constants are defined."""
        assert AIEvents.PROMPT == "ai.prompt"
        assert AIEvents.COMPLETION == "ai.completion"
        assert AIEvents.TOOL_INPUT == "ai.tool.input"
        assert AIEvents.TOOL_OUTPUT == "ai.tool.output"


class TestCreateLLMAttributes:
    """Tests for create_llm_attributes function."""

    def test_create_llm_attributes_basic(self):
        """Test creating basic LLM attributes."""
        attrs = create_llm_attributes(provider="openai", model_name="gpt-4")

        assert attrs[AIAttributes.OPERATION_TYPE] == "llm.invoke"
        assert attrs[AIAttributes.MODEL_PROVIDER] == "openai"
        assert attrs[AIAttributes.MODEL_NAME] == "gpt-4"

    def test_create_llm_attributes_with_tokens(self):
        """Test creating LLM attributes with token counts."""
        attrs = create_llm_attributes(
            provider="anthropic",
            model_name="claude-3",
            tokens_input=100,
            tokens_output=50,
        )

        assert attrs[AIAttributes.LLM_TOKENS_INPUT] == 100
        assert attrs[AIAttributes.LLM_TOKENS_OUTPUT] == 50
        assert attrs[AIAttributes.LLM_TOKENS_TOTAL] == 150

    def test_create_llm_attributes_with_extra_kwargs(self):
        """Test creating LLM attributes with additional kwargs."""
        attrs = create_llm_attributes(
            provider="openai",
            model_name="gpt-4",
            temperature=0.7,
            max_tokens=1000,
        )

        assert attrs["temperature"] == 0.7
        assert attrs["max_tokens"] == 1000

    def test_create_llm_attributes_partial_tokens(self):
        """Test creating LLM attributes with only input tokens."""
        attrs = create_llm_attributes(provider="openai", model_name="gpt-4", tokens_input=100)

        assert attrs[AIAttributes.LLM_TOKENS_INPUT] == 100
        assert AIAttributes.LLM_TOKENS_OUTPUT not in attrs
        assert AIAttributes.LLM_TOKENS_TOTAL not in attrs


class TestCreateToolAttributes:
    """Tests for create_tool_attributes function."""

    def test_create_tool_attributes_basic(self):
        """Test creating basic tool attributes."""
        attrs = create_tool_attributes(tool_name="weather_api", tool_type="http")

        assert attrs[AIAttributes.OPERATION_TYPE] == "tool.invoke"
        assert attrs[AIAttributes.TOOL_NAME] == "weather_api"
        assert attrs[AIAttributes.TOOL_TYPE] == "http"

    def test_create_tool_attributes_with_extra_kwargs(self):
        """Test creating tool attributes with additional kwargs."""
        attrs = create_tool_attributes(
            tool_name="calculator",
            tool_type="function",
            http_method="POST",
            http_url="https://api.example.com",
        )

        assert attrs["http_method"] == "POST"
        assert attrs["http_url"] == "https://api.example.com"


class TestValidateSpanName:
    """Tests for validate_span_name function."""

    def test_validate_span_name_valid_ai_patterns(self):
        """Test validation accepts valid ai.* patterns."""
        valid_names = [
            "ai.llm.invoke",
            "ai.tool.invoke",
            "ai.retrieval",
            "ai.embedding.generate",
        ]
        for name in valid_names:
            assert validate_span_name(name) is True

    def test_validate_span_name_valid_function_pattern(self):
        """Test validation accepts function.* pattern."""
        assert validate_span_name("function.process_data") is True
        assert validate_span_name("function.calculate") is True

    def test_validate_span_name_rejects_framework_concepts(self):
        """Test validation rejects framework concepts."""
        forbidden_names = [
            "ai.agent.run",
            "ai.chain.execute",
            "ai.workflow.process",
            "ai.pipeline.run",
        ]
        for name in forbidden_names:
            assert validate_span_name(name) is False

    def test_validate_span_name_rejects_invalid_patterns(self):
        """Test validation rejects invalid patterns."""
        invalid_names = [
            "invalid",
            "test.name",
            "llm.invoke",
            "agent.run",
        ]
        for name in invalid_names:
            assert validate_span_name(name) is False

    def test_validate_span_name_case_sensitive(self):
        """Test validation is case sensitive."""
        assert validate_span_name("AI.LLM.INVOKE") is False
        assert validate_span_name("ai.llm.invoke") is True

    def test_validate_span_name_empty_string(self):
        """Test validation rejects empty string."""
        assert validate_span_name("") is False

    def test_validate_span_name_with_numbers(self):
        """Test validation rejects names with numbers."""
        assert validate_span_name("ai.llm.invoke1") is False
        assert validate_span_name("function.process2") is True  # function.* allows anything

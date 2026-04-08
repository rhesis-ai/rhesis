"""Shared constants for telemetry and test execution context."""


class TestExecutionContext:
    """Constants for test execution context handling."""

    # Key for context in function inputs dict (executor level)
    CONTEXT_KEY = "_rhesis_test_context"

    # Field names in context dict
    class Fields:
        """Field names in the test execution context dictionary."""

        TEST_RUN_ID = "test_run_id"
        TEST_ID = "test_id"
        TEST_RESULT_ID = "test_result_id"
        TEST_CONFIGURATION_ID = "test_configuration_id"

    # OpenTelemetry span attribute names
    class SpanAttributes:
        """Span attribute names (OpenTelemetry semantic conventions)."""

        TEST_RUN_ID = "rhesis.test.run_id"
        TEST_ID = "rhesis.test.id"
        TEST_RESULT_ID = "rhesis.test.result_id"
        TEST_CONFIGURATION_ID = "rhesis.test.configuration_id"


class ConversationContext:
    """Constants for conversation context handling."""

    # Key for context in function inputs dict (executor level)
    CONTEXT_KEY = "_rhesis_conversation_context"

    # Maximum length for conversation I/O stored in span attributes.
    # Applied consistently wherever input/output is captured or injected.
    MAX_IO_LENGTH = 10000

    # Placeholder span_id used when building a synthetic OTEL parent
    # context to force trace_id inheritance across conversation turns.
    # Stripped by the exporter before export (see RhesisOTLPExporter).
    SYNTHETIC_PARENT_SPAN_ID = 0x00000000CAFECAFE

    # Field names in context dict
    class Fields:
        """Field names in the conversation context dictionary."""

        CONVERSATION_ID = "conversation_id"
        TRACE_ID = "trace_id"
        MAPPED_INPUT = "mapped_input"

    # OpenTelemetry span attribute names
    class SpanAttributes:
        """Span attribute names for conversation tracking."""

        CONVERSATION_ID = "rhesis.conversation.id"
        IS_TURN_ROOT = "rhesis.conversation.is_turn_root"
        CONVERSATION_INPUT = "rhesis.conversation.input"
        CONVERSATION_OUTPUT = "rhesis.conversation.output"

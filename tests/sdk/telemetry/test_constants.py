"""Tests for SDK telemetry constants."""

from rhesis.sdk.telemetry.constants import TestExecutionContext


def test_test_execution_context_has_context_key():
    """Test that TestExecutionContext has CONTEXT_KEY constant."""
    assert hasattr(TestExecutionContext, "CONTEXT_KEY")
    assert TestExecutionContext.CONTEXT_KEY == "_rhesis_test_context"


def test_test_execution_context_has_fields_class():
    """Test that TestExecutionContext has nested Fields class."""
    assert hasattr(TestExecutionContext, "Fields")
    assert hasattr(TestExecutionContext.Fields, "TEST_RUN_ID")
    assert hasattr(TestExecutionContext.Fields, "TEST_ID")
    assert hasattr(TestExecutionContext.Fields, "TEST_RESULT_ID")
    assert hasattr(TestExecutionContext.Fields, "TEST_CONFIGURATION_ID")


def test_test_execution_context_field_names():
    """Test that field names match expected values."""
    assert TestExecutionContext.Fields.TEST_RUN_ID == "test_run_id"
    assert TestExecutionContext.Fields.TEST_ID == "test_id"
    assert TestExecutionContext.Fields.TEST_RESULT_ID == "test_result_id"
    assert TestExecutionContext.Fields.TEST_CONFIGURATION_ID == "test_configuration_id"


def test_test_execution_context_has_span_attributes_class():
    """Test that TestExecutionContext has nested SpanAttributes class."""
    assert hasattr(TestExecutionContext, "SpanAttributes")
    assert hasattr(TestExecutionContext.SpanAttributes, "TEST_RUN_ID")
    assert hasattr(TestExecutionContext.SpanAttributes, "TEST_ID")
    assert hasattr(TestExecutionContext.SpanAttributes, "TEST_RESULT_ID")
    assert hasattr(TestExecutionContext.SpanAttributes, "TEST_CONFIGURATION_ID")


def test_test_execution_context_span_attribute_names():
    """Test that span attribute names follow OpenTelemetry conventions."""
    assert TestExecutionContext.SpanAttributes.TEST_RUN_ID == "rhesis.test.run_id"
    assert TestExecutionContext.SpanAttributes.TEST_ID == "rhesis.test.id"
    assert TestExecutionContext.SpanAttributes.TEST_RESULT_ID == "rhesis.test.result_id"
    assert (
        TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID == "rhesis.test.configuration_id"
    )


def test_backend_and_sdk_constants_match():
    """Test that backend and SDK constants are synchronized."""
    # Import backend constants for comparison
    from rhesis.backend.app.constants import (
        TestExecutionContext as BackendTestContext,
    )

    # Context key should match
    assert TestExecutionContext.CONTEXT_KEY == BackendTestContext.CONTEXT_KEY

    # Field names should match
    assert TestExecutionContext.Fields.TEST_RUN_ID == BackendTestContext.Fields.TEST_RUN_ID
    assert TestExecutionContext.Fields.TEST_ID == BackendTestContext.Fields.TEST_ID
    assert TestExecutionContext.Fields.TEST_RESULT_ID == BackendTestContext.Fields.TEST_RESULT_ID
    assert (
        TestExecutionContext.Fields.TEST_CONFIGURATION_ID
        == BackendTestContext.Fields.TEST_CONFIGURATION_ID
    )

    # Span attributes should match
    assert (
        TestExecutionContext.SpanAttributes.TEST_RUN_ID
        == BackendTestContext.SpanAttributes.TEST_RUN_ID
    )
    assert TestExecutionContext.SpanAttributes.TEST_ID == BackendTestContext.SpanAttributes.TEST_ID
    assert (
        TestExecutionContext.SpanAttributes.TEST_RESULT_ID
        == BackendTestContext.SpanAttributes.TEST_RESULT_ID
    )
    assert (
        TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID
        == BackendTestContext.SpanAttributes.TEST_CONFIGURATION_ID
    )

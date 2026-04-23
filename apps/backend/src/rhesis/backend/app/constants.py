import os
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


# Entity Types Enum - Unified for all entities including comments
class EntityType(Enum):
    GENERAL = "General"
    TEST = "Test"
    TEST_SET = "TestSet"
    TEST_RUN = "TestRun"
    TEST_RESULT = "TestResult"
    METRIC = "Metric"
    MODEL = "Model"
    PROMPT = "Prompt"
    BEHAVIOR = "Behavior"
    CATEGORY = "Category"
    TOPIC = "Topic"
    DIMENSION = "Dimension"
    DEMOGRAPHIC = "Demographic"
    TASK = "Task"
    PROJECT = "Project"
    SOURCE = "Source"
    CHUNK = "Chunk"
    TRACE = "Trace"

    @classmethod
    def get_value(cls, entity_type):
        """Get the string value of an entity type"""
        if isinstance(entity_type, cls):
            return entity_type.value
        return entity_type


# TestSetType Enum - DB-level test set classification aligned with initial_data.json type_lookup
class TestSetType(Enum):
    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"

    @classmethod
    def get_value(cls, test_set_type):
        """Get the string value of a test set type"""
        if isinstance(test_set_type, cls):
            return test_set_type.value
        return test_set_type

    @classmethod
    def from_string(cls, value: str):
        """Get enum from string value (case-insensitive, accepts snake_case and hyphenated).

        Maps both 'single_turn' and 'Single-Turn' to TestSetType.SINGLE_TURN, so API
        clients that use snake_case conventions are handled transparently.
        """
        if not value:
            return None
        # Normalize underscores to hyphens so snake_case aliases work (single_turn → single-turn)
        normalized = value.lower().replace("_", "-")
        for test_set_type in cls:
            if test_set_type.value.lower() == normalized:
                return test_set_type
        return None


# Metric TypeLookup values — aligned with initial_data.json and the frontend
class MetricBackendType:
    """Values for the BackendType type_lookup used on metrics."""

    CUSTOM = "custom"
    RHESIS = "rhesis"
    DEEPEVAL = "deepeval"
    RAGAS = "ragas"
    GARAK = "garak"


class MetricType:
    """Values for the MetricType type_lookup used on metrics."""

    CUSTOM_PROMPT = "custom-prompt"


# Display name stored in test_set.attributes["metadata"]["behaviors"] for adaptive testing sets
ADAPTIVE_TESTING_BEHAVIOR = "Adaptive Testing"


# Error messages
ERROR_INVALID_UUID = "Invalid UUID format in input parameters: {error}"
ERROR_TEST_SET_NOT_FOUND = "Test set with ID {test_set_id} not found"
ERROR_ENTITY_NOT_FOUND = "{entity} with ID {entity_id} not found"
ERROR_BULK_CREATE_FAILED = "Failed to create {entity}: {error}"
ERROR_ASSOCIATION_FAILED = "An error occurred while creating test set associations: {error}"
ERROR_DISASSOCIATION_FAILED = "Failed to remove test set associations: {error}"

# Success messages
SUCCESS_ASSOCIATIONS_CREATED = "Successfully associated {count} new test{plural}"
SUCCESS_ASSOCIATIONS_REMOVED = "Successfully removed {count} test associations"

# Default values
DEFAULT_BATCH_SIZE = 100
DEFAULT_PRIORITY = 1

# Model-related defaults
# Can be overridden via environment variables for flexible deployment
# Format: "provider/model_name" (e.g., "rhesis/rhesis-default")
DEFAULT_GENERATION_MODEL = os.getenv(
    "DEFAULT_GENERATION_MODEL", "rhesis/rhesis-default"
)  # Default model for test generation
DEFAULT_EVALUATION_MODEL = os.getenv(
    "DEFAULT_EVALUATION_MODEL", "rhesis/rhesis-default"
)  # Default model for evaluation (language-model-as-a-judge)
DEFAULT_EXECUTION_MODEL = os.getenv(
    "DEFAULT_EXECUTION_MODEL", "rhesis/rhesis-default"
)  # Default model for multi-turn test execution (Penelope)
DEFAULT_EMBEDDING_MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "vertex_ai/text-embedding-005")

DEFAULT_CONVERSATION_DEBOUNCE_SECONDS = int(
    os.getenv("DEFAULT_CONVERSATION_DEBOUNCE_SECONDS", "300")
)  # Seconds to wait before evaluating conversation-level metrics

# Rhesis API configuration
# Required for Rhesis system models to work
RHESIS_API_KEY = os.getenv("RHESIS_API_KEY", "your-rhesis-api-key")
RHESIS_BASE_URL = os.getenv("RHESIS_BASE_URL", "https://api.rhesis.ai")

# Test Result Status Mappings
# These define how test result status names map to passed/failed/error categories
# All status names are lowercase for case-insensitive matching
# Note: These align with the keyword matching used in services/stats/common.py
TEST_RESULT_STATUS_PASSED = frozenset(
    ["pass", "passed", "completed", "complete", "success", "successful", "finished", "done"]
)
TEST_RESULT_STATUS_FAILED = frozenset(["fail", "failed"])
TEST_RESULT_STATUS_ERROR = frozenset(
    [
        "error",  # Execution error
        "abort",
        "aborted",  # Execution aborted
        "cancel",
        "cancelled",
        "canceled",  # Execution cancelled
        "review",
        "pending",  # Awaiting review or execution
    ]
)


class TestResultStatus(str, Enum):
    """Exact DB status names for test results (written to the status table)."""

    PASS = "Pass"
    FAIL = "Fail"
    ERROR = "Error"


class ReviewTarget(str, Enum):
    """Review target types shared by TestResult and Trace review systems.

    Using str mixin so values work directly in string comparisons and JSON.
    """

    TEST_RESULT = "test_result"
    TRACE = "trace"
    TURN = "turn"
    METRIC = "metric"


LEGACY_TARGET_TEST = "test"

# Backward-compatible aliases used across the codebase
REVIEW_TARGET_TEST_RESULT = ReviewTarget.TEST_RESULT
REVIEW_TARGET_TRACE = ReviewTarget.TRACE
REVIEW_TARGET_TURN = ReviewTarget.TURN
REVIEW_TARGET_METRIC = ReviewTarget.METRIC
VALID_TARGET_TYPES = tuple(ReviewTarget)


class TestType(str, Enum):
    """Reserved test type values in the TypeLookup table.

    - SINGLE_TURN: Traditional single request-response tests
    - MULTI_TURN: Agentic multi-turn conversation tests using Penelope
    """

    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"


class OverallTestResult(str, Enum):
    """Aggregated result categories used in stats views and reporting.

    Multiple DB status names collapse into each bucket via the frozensets
    above and categorize_test_result_status(). A str enum so values work
    directly in SQL f-strings, ORM filters, and dict keys.
    """

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    ERROR = "error"


# Test Run Status Mappings (execution-level: did the run finish?)
# A "passed" run completed execution; "failed" means execution itself failed.
TEST_RUN_STATUS_PASSED = frozenset(
    ["completed", "complete", "finished", "done", "success", "successful"]
)
TEST_RUN_STATUS_FAILED = frozenset(["failed", "fail", "error", "aborted"])


def categorize_test_result_status(status_name: str) -> str:
    """Categorize a test result status name into an OverallTestResult bucket.

    Args:
        status_name: The status name (case-insensitive)

    Returns:
        One of OverallTestResult.PASSED, .FAILED, or .ERROR
    """
    if not status_name:
        return OverallTestResult.ERROR

    status_lower = status_name.lower()

    if status_lower in TEST_RESULT_STATUS_PASSED:
        return OverallTestResult.PASSED
    elif status_lower in TEST_RESULT_STATUS_FAILED:
        return OverallTestResult.FAILED
    else:
        return OverallTestResult.ERROR


# OpenTelemetry Semantic Convention attribute keys for AI/LLM spans.
# See: https://opentelemetry.io/docs/specs/semconv/gen-ai/
class AISpanAttributes:
    """Attribute keys stored in Trace.attributes (JSONB)."""

    OPERATION_TYPE = "ai.operation.type"
    MODEL_NAME = "ai.model.name"
    TOKENS_TOTAL = "ai.llm.tokens.total"


# Keys inside Trace.enriched_data (JSONB) populated by the enrichment service.
class EnrichedDataKeys:
    """Top-level and nested keys in Trace.enriched_data."""

    COSTS = "costs"
    TOTAL_COST_USD = "total_cost_usd"
    TOTAL_COST_EUR = "total_cost_eur"


# Test Execution Context Constants
class TestExecutionContext:
    """Constants for test execution context injection."""

    # Key for context in function kwargs dict
    CONTEXT_KEY = "_rhesis_test_context"

    # Field names in context dict
    class Fields:
        TEST_RUN_ID = "test_run_id"
        TEST_ID = "test_id"
        TEST_RESULT_ID = "test_result_id"
        TEST_CONFIGURATION_ID = "test_configuration_id"

    # Span attribute names (OpenTelemetry semantic conventions)
    class SpanAttributes:
        TEST_RUN_ID = "rhesis.test.run_id"
        TEST_ID = "rhesis.test.id"
        TEST_RESULT_ID = "rhesis.test.result_id"
        TEST_CONFIGURATION_ID = "rhesis.test.configuration_id"

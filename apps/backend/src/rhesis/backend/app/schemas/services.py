from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel, Field, model_validator


class GenerationConfig(BaseModel):
    """
    Configuration for test generation using ConfigSynthesizer.

    This schema mirrors the SDK's GenerationConfig to maintain consistency
    between frontend requests and SDK expectations.
    """

    generation_prompt: Optional[str] = None  # Describe what you want to test
    behaviors: Optional[List[str]] = None  # Behaviors to test
    categories: Optional[List[str]] = None  # Test categories
    topics: Optional[List[str]] = None  # Topics to cover
    additional_context: Optional[str] = None  # Additional context (JSON string)


class PromptRequest(BaseModel):
    prompt: str
    stream: bool = False


class TextResponse(BaseModel):
    text: str


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    response_format: Optional[str] = None
    stream: bool = False


class SourceData(BaseModel):
    """
    Source data for test generation.
    Only id is required. The backend will fetch name, description, and content from the database.
    """

    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class ChipState(BaseModel):
    """Chip state representing user preferences for test configuration."""

    label: str
    description: str
    active: bool
    category: str


class RatedSample(BaseModel):
    """Rated sample from user feedback."""

    prompt: str
    response: str
    rating: int
    feedback: Optional[str] = None


class IterationMessage(BaseModel):
    """Previous iteration message for context."""

    content: str
    timestamp: str
    chip_states: Optional[List[ChipState]] = None


class GenerateTestsRequest(BaseModel):
    """
    Unified request for test generation (both sampling and bulk).

    - For sampling: num_tests=5, run synchronously via /services/generate/tests
    - For bulk: num_tests=1000, run as background task via /test_sets/generate

    The config field contains the core generation parameters. Context information
    like chip_states, rated_samples, and previous_messages should be serialized
    into config.additional_context as a JSON string.
    """

    config: GenerationConfig
    num_tests: int = 5
    batch_size: int = 20
    sources: Optional[List[SourceData]] = None
    name: Optional[str] = None  # Used only for bulk generation to name the test set
    test_type: Optional[str] = "single_turn"


class TestPrompt(BaseModel):
    content: str
    language_code: str = "en"


class SourceInfo(BaseModel):
    source: str
    name: str
    description: Optional[str] = None
    content: Optional[str] = None


class TestMetadata(BaseModel):
    generated_by: str
    additional_info: Optional[Dict[str, Any]] = None
    sources: Optional[List[SourceInfo]] = None


class Test(BaseModel):
    prompt: TestPrompt
    behavior: str
    category: str
    topic: str
    metadata: TestMetadata


class GenerateTestsResponse(BaseModel):
    tests: List[Test]


class GenerateContentRequest(BaseModel):
    """Request for generating content with optional structured output.

    The schema parameter should follow the OpenAI JSON Schema format for structured outputs.
    This enables type-safe generation across different LLM providers.

    Example:
        {
            "prompt": "Generate a user profile",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"}
                },
                "required": ["name", "email"],
                "additionalProperties": False
            }
        }
    """

    prompt: str
    schema_: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="schema",
        description="Optional OpenAI JSON Schema for structured output validation",
    )

class GenerateEmbeddingRequest(BaseModel):
    text: str

class TestConfigRequest(BaseModel):
    prompt: str
    project_id: Optional[UUID4] = None
    previous_messages: Optional[List[IterationMessage]] = None


class TestConfigItem(BaseModel):
    name: str
    description: str
    active: bool


class TestConfigResponse(BaseModel):
    behaviors: List[TestConfigItem]
    topics: List[TestConfigItem]
    categories: List[TestConfigItem]


class GenerateMultiTurnTestsRequest(BaseModel):
    """Request for generating multi-turn test cases."""

    generation_prompt: str
    behavior: Optional[list[str]] = None
    category: Optional[list[str]] = None
    topic: Optional[list[str]] = None
    num_tests: int = 5


class MultiTurnTestConfiguration(BaseModel):
    """Multi-turn test configuration with goal, instructions, restrictions, and scenario."""

    goal: str
    instructions: str = ""  # Optional - how Penelope should conduct the test
    restrictions: str = ""  # Optional - forbidden behaviors for the target
    scenario: str = ""  # Optional - contextual framing for the test


class MultiTurnTest(BaseModel):
    """Multi-turn test case with structured configuration."""

    test_configuration: MultiTurnTestConfiguration
    behavior: str
    category: str
    topic: str
    test_type: str


class GenerateMultiTurnTestsResponse(BaseModel):
    """Response containing generated multi-turn test cases."""

    tests: List[MultiTurnTest]


# MCP Schemas


class ItemResult(BaseModel):
    """Minimal item metadata for search results."""

    id: str
    url: str
    title: str


class SearchMCPRequest(BaseModel):
    """Request to search MCP server."""

    query: str
    tool_id: str


class ExtractMCPRequest(BaseModel):
    """Request to extract MCP item content.

    Either 'id' or 'url' (or both) must be provided.
    The agent will use whichever is more appropriate for the provider.
    """

    id: Optional[str] = None
    url: Optional[str] = None
    tool_id: str

    @model_validator(mode="after")
    def validate_id_or_url(self):
        """Ensure at least one of id or url is provided."""
        if not self.id and not self.url:
            raise ValueError("Either 'id' or 'url' must be provided")
        return self


class QueryMCPRequest(BaseModel):
    """General-purpose request to query MCP server with custom task."""

    query: str
    tool_id: str
    system_prompt: Optional[str] = None
    max_iterations: Optional[int] = 10


class ExtractMCPResponse(BaseModel):
    """Response containing extracted content from MCP item."""

    content: str


class ToolCall(BaseModel):
    """Tool call in agent execution."""

    tool_name: str
    arguments: Dict[str, Any]


class ToolResult(BaseModel):
    """Result from tool execution."""

    tool_name: str
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None


class ExecutionStep(BaseModel):
    """Single step in agent execution history."""

    iteration: int
    reasoning: str
    action: str
    tool_calls: List[ToolCall]
    tool_results: List[ToolResult]


class QueryMCPResponse(BaseModel):
    """Response from general-purpose MCP query."""

    final_answer: str
    success: bool
    iterations_used: int
    max_iterations_reached: bool
    execution_history: List[ExecutionStep]


class TestMCPConnectionRequest(BaseModel):
    """Request to test MCP connection authentication.

    Either tool_id (for existing tools) OR provider_type_id + credentials
    (for non-existent tools) must be provided.
    For custom providers, tool_metadata is required when using provider_type_id.
    """

    tool_id: Optional[str] = None
    provider_type_id: Optional[UUID4] = None
    credentials: Optional[Dict[str, str]] = None
    tool_metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_request(self):
        """Ensure either tool_id OR (provider_type_id + credentials) is provided."""
        has_tool_id = self.tool_id is not None
        has_params = self.provider_type_id is not None and self.credentials is not None

        if not has_tool_id and not has_params:
            raise ValueError(
                "Either 'tool_id' OR ('provider_type_id' + 'credentials') must be provided"
            )

        if has_tool_id and has_params:
            raise ValueError(
                "Cannot provide both 'tool_id' and parameter-based fields. Use one approach."
            )

        return self


class TestMCPConnectionResponse(BaseModel):
    """Response from MCP connection authentication test."""

    is_authenticated: str  # "Yes" or "No"
    message: str
    additional_metadata: Optional[Dict[str, Any]] = None  # For provider-specific data like spaces


class CreateJiraTicketFromTaskRequest(BaseModel):
    """Request to create a Jira ticket from a task."""

    task_id: UUID4
    tool_id: str


class CreateJiraTicketFromTaskResponse(BaseModel):
    """Response from creating a Jira ticket."""

    issue_key: str  # e.g., "PROJ-123"
    issue_url: str  # Direct link to the created issue
    message: str


# Recent Activities Schemas
class ActivityOperation(str, Enum):
    """Type of operation performed on an entity."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class TimeRange(BaseModel):
    """Time range for bulk operations."""

    start: datetime
    end: datetime


class ActivityItem(BaseModel):
    """A single activity item or grouped bulk operation."""

    entity_type: str
    entity_id: Optional[UUID4] = None  # None for bulk operations
    operation: ActivityOperation
    timestamp: datetime
    user: Optional[Any] = None  # Full User schema from schemas.user
    entity_data: Optional[Dict[str, Any]] = None  # None for bulk operations

    # Bulk operation fields
    is_bulk: bool = False
    count: Optional[int] = None  # Number of entities in bulk operation
    time_range: Optional[TimeRange] = None  # Time span of bulk operation
    summary: Optional[str] = None  # Human-readable summary
    entity_ids: Optional[List[UUID4]] = None  # All entity IDs in bulk
    sample_entities: Optional[List[Dict[str, Any]]] = None  # First few entities as preview


class RecentActivitiesResponse(BaseModel):
    """Response containing recent activities across all trackable entities."""

    activities: List[ActivityItem]
    total: int  # Total number of activity groups (not individual activities)

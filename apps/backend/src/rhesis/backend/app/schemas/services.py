from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel, Field


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
    prompt: dict
    num_tests: int = 5
    sources: Optional[List[SourceData]] = None
    chip_states: Optional[List[ChipState]] = None
    rated_samples: Optional[List[RatedSample]] = None
    previous_messages: Optional[List[IterationMessage]] = None


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


class DocumentUploadResponse(BaseModel):
    path: str


class ExtractDocumentRequest(BaseModel):
    path: str


class ExtractDocumentResponse(BaseModel):
    content: str
    format: str


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
        None,
        alias="schema",
        description="Optional OpenAI JSON Schema for structured output validation",
    )


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


class MultiTurnPrompt(BaseModel):
    """Multi-turn prompt with goal, instructions, and restrictions."""

    goal: str
    instructions: List[str]
    restrictions: List[str]
    scenarios: List[str]


class MultiTurnTest(BaseModel):
    """Multi-turn test case with structured prompt."""

    prompt: MultiTurnPrompt
    behavior: str
    category: str
    topic: str


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
    server_name: str


class ExtractMCPRequest(BaseModel):
    """Request to extract MCP item content."""

    id: str
    server_name: str


class QueryMCPRequest(BaseModel):
    """General-purpose request to query MCP server with custom task."""

    query: str
    server_name: str
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

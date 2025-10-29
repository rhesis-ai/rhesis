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
    sample_size: int = 5
    project_id: Optional[UUID4] = None


class TestConfigItem(BaseModel):
    name: str
    description: str


class TestConfigResponse(BaseModel):
    behaviors: List[TestConfigItem]
    topics: List[TestConfigItem]
    categories: List[TestConfigItem]

from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel, Field

from rhesis.backend.app.schemas.documents import Document


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


class GenerateTestsRequest(BaseModel):
    prompt: dict
    num_tests: int = 5
    documents: Optional[List[Document]] = None


class TestPrompt(BaseModel):
    content: str
    language_code: str = "en"


class TestMetadata(BaseModel):
    generated_by: str
    additional_info: Optional[Dict[str, Any]] = None


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

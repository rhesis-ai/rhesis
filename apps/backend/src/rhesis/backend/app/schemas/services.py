from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

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


class DocumentSpecification(BaseModel):
    """Specification for a document that contains content."""
    name: str
    description: str
    content: str


class GenerateTestsRequest(BaseModel):
    """
    Request for generating insurance test cases, supporting two modes:
    1. Prompt-only: Generate tests based solely on the prompt
    2. Content-based: Generate tests using both prompt and provided document content
    
    Used by the JSON endpoint (/generate/tests/json).
    For file-based generation, use the /generate/tests/files endpoint.
    """
    prompt: str = Field(
        ...,
        description="The prompt describing what kind of tests to generate (e.g., 'Generate tests for auto insurance claims')"
    )
    num_tests: Optional[int] = Field(
        5,
        description="Number of test cases to generate (default: 5)"
    )
    documents: Optional[List[DocumentSpecification]] = Field(
        None, 
        description="Optional document specifications with content. If not provided, generates tests based on prompt only."
    )


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

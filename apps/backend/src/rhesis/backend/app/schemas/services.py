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
    """Specification for a document that can be referenced by path or contain direct content."""
    name: str
    description: Optional[str] = None
    content: Optional[str] = Field(None, description="Direct text content of the document")
    path: Optional[str] = Field(None, description="File path to the document")


class GenerateTestsRequest(BaseModel):
    """
    Request for generating tests with optional document context.
    
    Used by the JSON endpoint (/generate/tests/json).
    For file uploads, use the form-based endpoint (/generate/tests).
    """
    prompt: str
    num_tests: Optional[int] = 5
    documents: Optional[List[DocumentSpecification]] = Field(
        None, 
        description="Document specifications (metadata). For file uploads, use the form-based endpoint."
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

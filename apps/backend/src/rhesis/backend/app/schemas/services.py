from typing import List, Optional, Dict, Any

from pydantic import BaseModel, field_validator


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


class Document(BaseModel):
    name: str
    description: str
    path: Optional[str] = None
    content: Optional[str] = None

    @field_validator("path", "content", mode="after")
    def require_path_or_content(cls, v, values, field):
        # Only run this check once, for one of the fields
        if field.name == "content":
            path = values.get("path")
            content = v
            if not path and not content:
                raise ValueError("Either 'path' or 'content' must be provided.")
        return v


class GenerateTestsRequest(BaseModel):
    prompt: str
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
    """Response model for document upload endpoint. Returns the full path where the document is stored."""
    path: str

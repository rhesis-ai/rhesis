from typing import Any, Dict, List, Optional

from pydantic import BaseModel

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
    prompt: str
    schema: Optional[Dict[str, Any]] = None


class TestConfigRequest(BaseModel):
    prompt: str


class TestConfigResponse(BaseModel):
    behaviors: List[str]
    topics: List[str]
    categories: List[str]
    scenarios: List[str]

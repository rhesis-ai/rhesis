import os
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, model_validator
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
    path: str

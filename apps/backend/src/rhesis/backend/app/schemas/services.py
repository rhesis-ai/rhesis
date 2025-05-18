from typing import List, Optional

from pydantic import BaseModel


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

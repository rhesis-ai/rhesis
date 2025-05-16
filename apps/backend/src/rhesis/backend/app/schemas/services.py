from typing import List

from pydantic import BaseModel


class PromptRequest(BaseModel):
    prompt: str
    stream: bool = False


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    response_format: str = "json_object"  # default to JSON response
    stream: bool = False

from typing import List, Optional

from pydantic import BaseModel


class InferenceRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    stream: bool = False
    system_prompt: Optional[str] = None


class GenerationResponse(BaseModel):
    generated_text: str
    tokens_generated: int
    generation_time_seconds: float


class Message(BaseModel):
    """Message format"""

    role: Optional[str] = None
    content: str


class GenerateRequest(BaseModel):
    """Request format"""

    messages: List[Message]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512
    stream: bool = False
    repetition_penalty: Optional[float] = None  # Penalty for repetition (>1.0 = penalty)
    top_p: Optional[float] = None  # Nucleus sampling parameter
    top_k: Optional[int] = None  # Top-k sampling parameter

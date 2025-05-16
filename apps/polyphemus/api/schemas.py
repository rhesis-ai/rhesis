from pydantic import BaseModel
from typing import Optional

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
import asyncio
import json
import random
import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI
from jsf import JSF
from pydantic import BaseModel

HOST = "0.0.0.0"
PORT = 18080
BASE_DELAY_SECONDS = 2.0
RANDOM_DELAY_MAX_SECONDS = 0.5
DEFAULT_MODEL = "mock-llm"

app = FastAPI(title="Mock OpenAI LLM")


class ChatCompletionRequest(BaseModel):
    model: str = DEFAULT_MODEL
    messages: list[dict[str, Any]]
    stream: bool = False
    response_format: Optional[dict[str, Any]] = None


def _build_content(text: str, response_format: Optional[dict[str, Any]]) -> str:
    """Return the assistant content, honoring an OpenAI ``response_format`` request.

    ``json_schema`` -> random data matching the schema; ``json_object`` -> a generic random
    object; anything else -> the uppercased prompt text (legacy behavior).
    """
    response_format = response_format or {}
    fmt_type = response_format.get("type")

    if fmt_type == "json_schema":
        schema = (response_format.get("json_schema") or {}).get("schema") or {}
        if schema:
            return json.dumps(JSF(schema).generate(), default=str)

    if fmt_type == "json_object":
        return json.dumps({"response": text})

    return text.upper()


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> dict[str, Any]:
    await asyncio.sleep(BASE_DELAY_SECONDS + random.random() * RANDOM_DELAY_MAX_SECONDS)

    text = "\n".join(str(m.get("content", "")) for m in request.messages if m.get("content"))
    content = _build_content(text, request.response_format)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(text.split()),
            "completion_tokens": len(content.split()),
            "total_tokens": len(text.split()) + len(content.split()),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)

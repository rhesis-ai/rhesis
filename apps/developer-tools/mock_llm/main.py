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


TURN_FIELD_PAIRS = (
    ("test_configuration_min_turns", "test_configuration_max_turns"),
    ("min_turns", "max_turns"),
)
TURN_MIN = 1
TURN_MAX = 50


def _clamp_turn(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = TURN_MIN
    return max(TURN_MIN, min(TURN_MAX, number))


def _fix_turn_bounds_in_dict(data: dict[str, Any]) -> None:
    for min_key, max_key in TURN_FIELD_PAIRS:
        if min_key not in data or max_key not in data:
            continue
        lo = _clamp_turn(data[min_key])
        hi = _clamp_turn(data[max_key])
        if lo > hi:
            lo, hi = hi, lo
        data[min_key] = lo
        data[max_key] = hi


def _fix_schema_constraints(value: Any) -> Any:
    if isinstance(value, dict):
        fixed = {k: _fix_schema_constraints(v) for k, v in value.items()}
        _fix_turn_bounds_in_dict(fixed)
        return fixed
    if isinstance(value, list):
        return [_fix_schema_constraints(item) for item in value]
    return value


def _no_empty_strings(value: Any) -> Any:
    if isinstance(value, str):
        return value or "mock"
    if isinstance(value, dict):
        return {k: _no_empty_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_no_empty_strings(v) for v in value]
    return value


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
            generated = _no_empty_strings(JSF(schema).generate())
            return json.dumps(_fix_schema_constraints(generated), default=str)

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

"""
Polyphemus service - Vertex AI endpoint proxy.
This module provides business logic for calling Vertex AI endpoints.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from rhesis.polyphemus.schemas import GenerateRequest, Message

logger = logging.getLogger("rhesis-polyphemus")

# Thread pool executor for running blocking operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="polyphemus-vertex")


def _extract_prompt_from_messages(messages: List[Message]) -> tuple[str, Optional[str]]:
    """
    Extract prompt and system prompt from messages array.

    Args:
        messages: List of message objects

    Returns:
        tuple: (prompt, system_prompt)
    """
    prompt_parts = []
    system_prompt = None

    for msg in messages:
        content = msg.content.strip()
        if not content:
            continue

        # Check if it's a system message
        if msg.role == "system":
            system_prompt = content
        else:
            # For user/assistant messages, append to prompt
            prompt_parts.append(content)

    # Combine all non-system messages into a single prompt
    prompt = "\n".join(prompt_parts) if prompt_parts else ""

    return prompt, system_prompt


def _get_vertex_access_token() -> str:
    """
    Get an access token using Google Application Default Credentials (ADC).

    Supports:
    - Cloud Run: uses metadata server automatically (no env var needed)
    - Local dev with gcloud: uses ~/.config/gcloud/application_default_credentials.json
    - GOOGLE_APPLICATION_CREDENTIALS as file path
    - GOOGLE_APPLICATION_CREDENTIALS as base64-encoded JSON (decoded to temp file)
    """
    import google.auth
    import google.auth.transport.requests

    # Handle base64-encoded GOOGLE_APPLICATION_CREDENTIALS (common in .env files)
    creds_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_env:
        # Check if it looks like base64 (long string, no path separators)
        if len(creds_env) > 500 and "/" not in creds_env and "\\" not in creds_env:
            try:
                # Decode base64 and write to temp file
                decoded = base64.b64decode(creds_env, validate=True)
                creds_json = json.loads(decoded)

                # Create deterministic temp file based on hash
                creds_hash = hashlib.sha256(creds_env.encode()).hexdigest()[:16]
                temp_dir = Path(tempfile.gettempdir())
                temp_file = temp_dir / f"polyphemus_gcp_creds_{creds_hash}.json"

                with open(temp_file, "w") as f:
                    json.dump(creds_json, f)

                # Update env var to point to temp file
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(temp_file)
                logger.info(f"Decoded base64 credentials to {temp_file}")
            except (base64.binascii.Error, json.JSONDecodeError, OSError) as e:
                logger.warning(
                    f"GOOGLE_APPLICATION_CREDENTIALS looks like base64 but failed to decode: {e}"
                )

    # Get credentials via ADC
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if hasattr(credentials, "with_scopes") and credentials.requires_scopes:
        credentials = credentials.with_scopes(["https://www.googleapis.com/auth/cloud-platform"])
    request_adc = google.auth.transport.requests.Request()
    credentials.refresh(request_adc)
    return credentials.token


def _build_vertex_request_body(
    messages: List[Message],
    max_tokens: int = 1024,
    temperature: float = 0.6,
    top_p: float = 1.0,
    top_k: Optional[int] = None,
    json_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build JSON body for Vertex AI rawPredict (vLLM OpenAI chat format)."""
    body: Dict[str, Any] = {
        "messages": [{"role": (m.role or "user"), "content": m.content} for m in messages],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    if top_k is not None and top_k >= 0:
        body["top_k"] = top_k
    if json_schema is not None:
        body["json_schema"] = json_schema
    return body


async def generate_text_via_vertex_endpoint(
    request: GenerateRequest,
    *,
    endpoint_id: str,
    project_id: str,
    location: str = "us-central1",
    timeout_seconds: float = 600.0,
) -> Dict:
    """
    Generate text by calling a Vertex AI endpoint (rawPredict, e.g. vLLM).

    Uses Application Default Credentials for authentication (same as gcloud).
    Request/response follow OpenAI chat completions format expected by vLLM.

    Args:
        request: GenerateRequest with messages and generation parameters.
        endpoint_id: Vertex AI endpoint ID.
        project_id: Google Cloud project ID.
        location: Vertex AI region (default us-central1).
        timeout_seconds: HTTP timeout for the prediction request.

    Returns:
        dict: Rhesis API format with choices, model, and usage.

    Raises:
        ValueError: If prompt is empty.
        RuntimeError: If the endpoint call fails.
    """
    prompt, _ = _extract_prompt_from_messages(request.messages)
    if not prompt:
        raise ValueError("At least one message with content is required")

    # Get parameters with defaults
    max_tokens = request.max_tokens or 1024
    temperature = request.temperature if request.temperature is not None else 0.6
    top_p = request.top_p if request.top_p is not None else 1.0
    top_k = request.top_k

    # Validate and clamp parameters to Vertex AI requirements
    # temperature must be > 0
    if temperature <= 0:
        logger.warning(f"temperature={temperature} invalid, using 0.6")
        temperature = 0.6

    # top_p must be in (0, 1] (greater than 0, up to and including 1)
    if top_p <= 0 or top_p > 1:
        logger.warning(f"top_p={top_p} invalid (must be in (0,1]), using 1.0")
        top_p = 1.0

    # top_k: only include if explicitly set and >= 0; -1 or None means don't send it
    if top_k is not None and top_k < 0:
        top_k = None

    body = _build_vertex_request_body(
        messages=request.messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        json_schema=request.json_schema,
    )

    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{location}/endpoints/{endpoint_id}:rawPredict"
    )

    loop = asyncio.get_running_loop()
    token = await loop.run_in_executor(_executor, _get_vertex_access_token)

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    if response.status_code != 200:
        logger.error(f"Vertex endpoint error: status={response.status_code}, body={response.text}")
        raise RuntimeError(f"Vertex AI endpoint failed: {response.status_code} - {response.text}")

    data = response.json()

    # Map vLLM/OpenAI-style response to Rhesis API format
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("Vertex AI endpoint returned no choices")
    first = choices[0]
    message = first.get("message", {})
    content = message.get("content", "") or ""
    usage = data.get("usage", {})
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))

    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": first.get("finish_reason", "stop"),
            }
        ],
        "model": request.model or f"vertex/{endpoint_id}",
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }

"""
Polyphemus service - Vertex AI endpoint proxy.
This module provides business logic for calling Vertex AI endpoints.
"""

import asyncio
import base64
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from rhesis.polyphemus.schemas import GenerateRequest, Message

logger = logging.getLogger("rhesis-polyphemus")

# User-facing model aliases mapped to internal config (env vars: endpoint IDs, etc.)
POLYPHEMUS_MODEL_ALIASES = ("polyphemus-default",)

POLYPHEMUS_MODELS: Dict[str, Optional[str]] = {
    "polyphemus-default": os.getenv("POLYPHEMUS_DEFAULT_MODEL")
}

DEFAULT_MODEL_ALIAS = "polyphemus-default"


def resolve_model(user_model: Optional[str]) -> str:
    """
    Resolve a user-provided model alias to the internal config value (from env).

    Allowed aliases: polyphemus-default, polyphemus-opus, polyphemus-flash-001.
    Also accepts "default" as shorthand for "polyphemus-default".
    If user_model is None or empty, returns the internal value for polyphemus-default.

    Raises:
        ValueError: If user_model is not None and not one of the allowed aliases,
            or if the resolved env value is missing.
    """
    alias = user_model if user_model else DEFAULT_MODEL_ALIAS
    # Accept "default" as shorthand for "polyphemus-default"
    if alias == "default":
        alias = DEFAULT_MODEL_ALIAS
    if alias not in POLYPHEMUS_MODEL_ALIASES:
        raise ValueError(
            f"Invalid model: {alias!r}. Allowed: {', '.join(POLYPHEMUS_MODEL_ALIASES)}."
        )
    internal = POLYPHEMUS_MODELS.get(alias)
    if not internal:
        raise ValueError(
            f"Model {alias!r} is not configured. "
            f"Set the corresponding POLYPHEMUS_*_MODEL environment variable."
        )
    return internal


# Thread pool executor for running blocking operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="polyphemus-vertex")

# Shared HTTP client — one connection pool reused across all requests
_http_client = httpx.AsyncClient()

# GCP credentials cache — tokens are valid for 1 hour; refresh 5 min before expiry
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)
_credentials_lock = threading.Lock()
_cached_credentials = None

# Retry configuration for transient Vertex AI errors
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_BASE = 1.0  # seconds; doubles each retry: 1s, 2s


def _get_vertex_access_token() -> str:
    """
    Return a valid GCP access token, refreshing only when necessary.

    Credentials are cached at module level and reused until 5 minutes before
    expiry (~55-minute effective lifetime per token). Thread-safe via a lock.

    Supports:
    - Cloud Run: metadata server (no env var needed)
    - Local dev with gcloud: application_default_credentials.json
    - GOOGLE_APPLICATION_CREDENTIALS as a file path
    - GOOGLE_APPLICATION_CREDENTIALS as base64-encoded JSON (loaded in-memory)
    """
    global _cached_credentials

    import google.auth
    import google.auth.transport.requests

    with _credentials_lock:
        # Reuse cached credentials if the token is still fresh
        if _cached_credentials is not None:
            expiry = getattr(_cached_credentials, "expiry", None)
            if expiry is not None:
                # expiry from google-auth is a naive UTC datetime; make it aware
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < expiry - _TOKEN_EXPIRY_BUFFER:
                    return _cached_credentials.token

        request_adc = google.auth.transport.requests.Request()

        # Handle base64-encoded GOOGLE_APPLICATION_CREDENTIALS (common in .env files).
        # Load in-memory to avoid writing a world-readable temp file.
        creds_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_env and len(creds_env) > 500 and "/" not in creds_env and "\\" not in creds_env:
            try:
                from google.oauth2 import service_account

                decoded = base64.b64decode(creds_env, validate=True)
                creds_json = json.loads(decoded)
                credentials = service_account.Credentials.from_service_account_info(
                    creds_json, scopes=_SCOPES
                )
                logger.info("Loaded GCP credentials from base64-encoded env var (in-memory)")
                credentials.refresh(request_adc)
                _cached_credentials = credentials
                return credentials.token
            except (base64.binascii.Error, json.JSONDecodeError, Exception) as e:
                logger.warning(
                    f"GOOGLE_APPLICATION_CREDENTIALS looks like base64 but failed to decode: {e}"
                )

        # Fall back to Application Default Credentials (Cloud Run metadata server,
        # gcloud ADC file, or GOOGLE_APPLICATION_CREDENTIALS as a file path).
        credentials, _ = google.auth.default(scopes=_SCOPES)
        if hasattr(credentials, "with_scopes") and credentials.requires_scopes:
            credentials = credentials.with_scopes(_SCOPES)
        credentials.refresh(request_adc)
        _cached_credentials = credentials
        return credentials.token


def _build_vertex_request_body(
    messages: List[Message],
    *,
    max_tokens: Optional[int] = None,
    temperature: float = 0.6,
    top_p: float = 1.0,
    top_k: Optional[int] = None,
    json_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build JSON body for Vertex AI rawPredict (vLLM OpenAI chat format)."""
    body: Dict[str, Any] = {
        "messages": [{"role": (m.role or "user"), "content": m.content} for m in messages],
        "temperature": temperature,
        "top_p": top_p,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
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
    timeout_seconds: float = 120.0,
) -> Dict:
    """
    Generate text by calling a Vertex AI endpoint (rawPredict, e.g. vLLM).

    Uses Application Default Credentials for authentication (same as gcloud).
    Request/response follow OpenAI chat completions format expected by vLLM.
    Retries up to _MAX_ATTEMPTS times on transient errors with exponential backoff.

    Args:
        request: GenerateRequest with messages and generation parameters.
        endpoint_id: Vertex AI endpoint ID.
        project_id: Google Cloud project ID.
        location: Vertex AI region (default us-central1).
        timeout_seconds: HTTP timeout per attempt (default 120s).

    Returns:
        dict: Rhesis API format with choices, model, and usage.

    Raises:
        ValueError: If no non-system message with content is provided.
        RuntimeError: If the endpoint call fails after all retry attempts.
    """
    if not any(m.content.strip() for m in request.messages if m.role != "system"):
        raise ValueError("At least one non-system message with content is required")

    resolved_model = resolve_model(request.model)

    # Get parameters with defaults (max_tokens is optional; only passed when provided)
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
        max_tokens=request.max_tokens,
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

    response = None
    last_error: Optional[Exception] = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = await _http_client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=timeout_seconds,
            )
            if response.status_code not in _RETRYABLE_STATUSES:
                break  # success or non-retryable client error
            last_error = RuntimeError(
                f"Vertex AI endpoint failed: {response.status_code} - {response.text}"
            )
        except httpx.TransportError as exc:
            last_error = exc
            response = None

        if attempt < _MAX_ATTEMPTS - 1:
            wait = _RETRY_BACKOFF_BASE * (2**attempt)
            logger.warning(
                "Vertex AI transient error on attempt %d/%d, retrying in %.1fs: %s",
                attempt + 1,
                _MAX_ATTEMPTS,
                wait,
                last_error,
            )
            await asyncio.sleep(wait)

    if response is None:
        raise RuntimeError(
            f"Vertex AI endpoint unreachable after {_MAX_ATTEMPTS} attempts"
        ) from last_error

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
        "model": resolved_model,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }

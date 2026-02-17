"""
Polyphemus service - Model instance management and generation logic.
This module provides model instances and business logic for inference.
Models are loaded lazily on first request to avoid blocking application startup.
Models are selected based on user request (model parameter in generate endpoint).
Default model is LazyModelLoader.
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import httpx

from rhesis.polyphemus.models import LazyModelLoader
from rhesis.polyphemus.schemas import GenerateRequest, Message
from rhesis.sdk.models import BaseLLM

logger = logging.getLogger("rhesis-polyphemus")

# Model cache: maps model identifier to model instance
_model_cache: dict[str, BaseLLM] = {}

# Async lock for thread-safe model loading
_model_lock = asyncio.Lock()

# Thread pool executor for running blocking operations
# Increased workers for better throughput with async requests
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="polyphemus-generate")

# Default model identifier - can be overridden via environment variable
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "huggingface/distilgpt2")


def is_model_loaded(model_name: Optional[str] = None) -> bool:
    """
    Check if a model instance is initialized and loaded.
    Non-blocking check that doesn't trigger model loading.

    Args:
        model_name: Model identifier. If None, checks default model.

    Returns:
        bool: True if model is loaded, False otherwise
    """
    model_id = model_name or DEFAULT_MODEL
    if model_id not in _model_cache:
        return False

    model = _model_cache[model_id]
    # Check if model has model/tokenizer attributes (HuggingFace models)
    if hasattr(model, "model") and hasattr(model, "tokenizer"):
        return model.model is not None and model.tokenizer is not None
    # For other model types, assume loaded if in cache
    return True


async def get_polyphemus_instance(model_name: Optional[str] = None) -> BaseLLM:
    """
    Get or create a model instance with lazy async initialization.

    The model is only loaded on first access, not at module import time.
    This prevents blocking application startup and aligns with the design intent
    that models should load on first request.

    Models are cached by model identifier, so subsequent requests for the same
    model will reuse the cached instance.

    Args:
        model_name: Model identifier in format "provider/model" or just model name.
            If None, uses default model (LazyModelLoader with huggingface/distilgpt2).

    Returns:
        BaseLLM: The model instance
    """
    # Use default model if not provided
    model_id = model_name or DEFAULT_MODEL

    # Check if model is already cached (fast path)
    if model_id in _model_cache:
        logger.debug(f"Using cached model instance for: {model_id}")
        return _model_cache[model_id]

    # Model not in cache - need to load it
    async with _model_lock:
        # Double-check pattern: another coroutine might have initialized it while we waited
        if model_id in _model_cache:
            logger.debug(f"Model was cached by another coroutine: {model_id}")
            return _model_cache[model_id]

        logger.info(f"Initializing LazyModelLoader with model: {model_id} (first time)")

        try:
            # Create LazyModelLoader instance with auto_loading=False to defer model loading
            model_instance = LazyModelLoader(model_name=model_id, auto_loading=False)

            # Load model asynchronously in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, model_instance.load_model)

            # Cache the model instance
            _model_cache[model_id] = model_instance

            logger.info(
                f"Model instance cached and ready: {model_id}, "
                f"model loaded: {getattr(model_instance, 'model', None) is not None}, "
                f"cache size: {len(_model_cache)}"
            )
            return _model_cache[model_id]
        except Exception as load_error:
            # If model loading fails, log error
            logger.error(f"Failed to load model '{model_id}': {str(load_error)}")
            # Only fall back if this wasn't already the default model
            if model_id != DEFAULT_MODEL:
                # Exit lock context before recursive call to avoid deadlock
                pass
            else:
                # If default also fails, re-raise the error
                raise

    # If we get here, the requested model failed and we should fall back to default
    # (lock is now released, safe to make recursive call)
    if model_id != DEFAULT_MODEL:
        logger.info(f"Falling back to default model: {DEFAULT_MODEL}")
        default_model = await get_polyphemus_instance(model_name=None)
        # Cache the default model under the requested model_id to avoid retrying failures
        _model_cache[model_id] = default_model
        return default_model
    else:
        # This shouldn't happen, but if it does, raise the original error
        raise RuntimeError(f"Failed to load default model: {DEFAULT_MODEL}")


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
    import base64
    import hashlib
    import json
    import tempfile
    from pathlib import Path

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
    )

    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{location}/endpoints/{endpoint_id}:rawPredict"
    )

    loop = asyncio.get_event_loop()
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


async def generate_text(request: GenerateRequest) -> Dict:
    """
    Generate text using the specified model.

    This is the main business logic for text generation. It handles:
    - Extracting prompts from messages
    - Loading/getting the model instance
    - Building generation parameters
    - Executing generation with retry logic
    - Formatting the response

    Args:
        request: GenerateRequest containing messages, model, and generation parameters

    Returns:
        dict: Rhesis API format response with choices, model, and usage

    Raises:
        ValueError: If prompt is empty
        RuntimeError: If model generation fails
    """
    # Extract prompt and system prompt from messages
    prompt, system_prompt = _extract_prompt_from_messages(request.messages)

    if not prompt:
        raise ValueError("At least one message with content is required")

    # Get generation parameters
    temperature = request.temperature or 0.7
    max_tokens = request.max_tokens or 512
    repetition_penalty = (
        request.repetition_penalty if request.repetition_penalty is not None else 1.2
    )
    top_p = request.top_p if request.top_p is not None else 0.9
    top_k = request.top_k

    # Performance timing: Track total request time
    start_total = time.time()

    # Get model instance based on request (lazy initialization on first access)
    # Note: get_polyphemus_instance has internal fallback logic that masks failures
    # We need to check if the returned model actually matches what was requested
    requested_model_name = request.model
    start_model_load = time.time()
    try:
        llm = await get_polyphemus_instance(model_name=requested_model_name)
        model_load_time = time.time() - start_model_load
        logger.info(f"⏱️ Model load/get time: {model_load_time:.2f}s")

        # Check if get_polyphemus_instance fell back internally to default
        # by comparing the returned model's name with what was requested
        returned_model_name = getattr(llm, "_model_name", getattr(llm, "model_name", None))

        # If a non-default model was requested but a different model was returned,
        # a fallback occurred. Only set actual_model_name if models match.
        if requested_model_name and returned_model_name != requested_model_name:
            # Fallback to default happened internally
            logger.info(
                f"Model fallback detected: requested '{requested_model_name}' "
                f"but received '{returned_model_name}' (likely default)"
            )
            actual_model_name = None
        else:
            # Either no model was requested (use default) or requested model loaded
            actual_model_name = requested_model_name
    except Exception as model_error:
        model_load_time = time.time() - start_model_load
        logger.warning(
            f"Failed to load model '{requested_model_name}', using default: {str(model_error)}"
        )
        llm = await get_polyphemus_instance(model_name=None)
        actual_model_name = None  # Indicate fallback to default
        logger.info(f"⏱️ Model load/get time (with fallback): {model_load_time:.2f}s")

    logger.info(
        f"Generating with prompt: {prompt[:100]}..., "
        f"system_prompt: {system_prompt}, max_tokens: {max_tokens}"
    )

    # Check if model is loaded before generating (for HuggingFace models)
    if hasattr(llm, "model") and hasattr(llm, "tokenizer"):
        if llm.model is None or llm.tokenizer is None:
            raise RuntimeError("Model or tokenizer not loaded. Please check model initialization.")

    # Build generation kwargs with optimizations for FP16 and GPU performance
    # Fix max_tokens: Respect user input, use default only if not provided
    max_new_tokens = max_tokens if max_tokens else 2048
    gen_kwargs = {
        "prompt": prompt,
        "system_prompt": system_prompt,
        "temperature": max(temperature, 0.7),  # Ensure minimum temperature
        "max_new_tokens": max_new_tokens,  # Use user-provided max_tokens or default
        "min_new_tokens": 5,  # Force at least 5 new tokens
        "do_sample": True,  # Enable sampling (required for temperature)
        "top_p": top_p,  # Nucleus sampling
        "repetition_penalty": repetition_penalty,  # Penalize repetition
        "no_repeat_ngram_size": 3,  # Prevent repeating 3-grams
    }

    # Add top_k if provided
    if top_k is not None:
        gen_kwargs["top_k"] = top_k

    logger.info(f"⏱️ Generation config: max_new_tokens={max_new_tokens}, temperature={temperature}")

    # Run the blocking generate call in a thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    start_generation = time.time()
    try:
        response = await loop.run_in_executor(
            _executor,
            lambda: llm.generate(**gen_kwargs),
        )
        generation_time = time.time() - start_generation
        logger.info(f"⏱️ Generation time: {generation_time:.2f}s")
    except Exception as gen_error:
        generation_time = time.time() - start_generation
        logger.error(f"Generation error: {str(gen_error)}", exc_info=True)
        logger.info(f"⏱️ Generation time (failed): {generation_time:.2f}s")
        raise RuntimeError(f"Generation failed: {str(gen_error)}")

    # Log response details
    response_length = len(response) if isinstance(response, str) else 0
    logger.info(
        f"Generated response type: {type(response)}, "
        f"length: {response_length}, "
        f"content: {repr(response[:200]) if response else 'None'}"
    )

    # Calculate total request time
    total_time = time.time() - start_total
    logger.info(f"⏱️ Total request time: {total_time:.2f}s")

    # Ensure response is a string and not empty
    if not response or (isinstance(response, str) and not response.strip()):
        logger.warning(
            f"Empty response from model. Prompt: {prompt[:50]}..., Response: {repr(response)}"
        )
        # Try generating again with different parameters to break repetition
        try:
            logger.info("Retrying generation with adjusted parameters to prevent repetition...")
            retry_gen_kwargs = {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": 0.9,  # Higher temperature for more diversity
                "max_new_tokens": max(max_tokens, 50),  # Ensure minimum tokens
                "min_new_tokens": 10,  # Force at least 10 new tokens
                "do_sample": True,
                "top_p": 0.95,
                "top_k": 50,  # Top-k sampling
                # Stronger penalty on retry to break repetition loops
                "repetition_penalty": max(repetition_penalty, 1.3),
                "no_repeat_ngram_size": 4,  # Prevent repeating 4-grams
            }
            response = await loop.run_in_executor(
                _executor,
                lambda: llm.generate(**retry_gen_kwargs),
            )
            logger.info(f"Retry response: {repr(response[:100]) if response else 'None'}")
        except Exception as retry_error:
            logger.error(f"Retry generation also failed: {str(retry_error)}")
            response = None

        if not response or (isinstance(response, str) and not response.strip()):
            logger.error("Model returned empty response even after retry")
            response = (
                "I'm sorry, I couldn't generate a response. The model returned an empty output."
            )
    elif isinstance(response, str):
        # Strip only leading/trailing whitespace, keep the content
        response = response.strip()
    else:
        # Convert to string if it's not already
        response = str(response).strip()

    # Use the actual model name we tracked earlier
    # If user provided a model and it was used, return that; otherwise return default
    if actual_model_name:
        response_model_name = actual_model_name
    else:
        # Fallback to default was used
        response_model_name = DEFAULT_MODEL

    # Log which model was actually used
    logger.info(f"Response using model: {response_model_name}")

    # Calculate token counts (simple word-based approximation)
    prompt_tokens = len(prompt.split()) if prompt else 0
    completion_tokens = len(response.split()) if response else 0

    # Return Rhesis API format
    return {
        "choices": [
            {"message": {"role": "assistant", "content": response}, "finish_reason": "stop"}
        ],
        "model": response_model_name,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }

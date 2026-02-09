"""
Polyphemus service - Model instance management and generation logic.
This module provides model instances and business logic for inference.
Models are loaded lazily on first request to avoid blocking application startup.
Models are selected based on user request (model parameter in generate endpoint).

Supports two inference engines:
- vLLM (default): High-performance GPU inference with 10-20x speedup
- Transformers (fallback): Standard HuggingFace via SDK

Set INFERENCE_ENGINE=vllm (default) or INFERENCE_ENGINE=transformers.
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Union

from rhesis.polyphemus.models import (
    INFERENCE_ENGINE,
    LazyModelLoader,
    VLLMModelLoader,
)
from rhesis.polyphemus.schemas import GenerateRequest, Message

logger = logging.getLogger("rhesis-polyphemus")

# Model cache: maps model identifier to model instance
_model_cache: dict[str, Union[VLLMModelLoader, LazyModelLoader]] = {}

# Async lock for thread-safe model loading
_model_lock = asyncio.Lock()

# Thread pool executor for running blocking operations
# vLLM: generation is blocking but fast (5-15s for 2k tokens)
# Transformers: generation is blocking and slower
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="polyphemus-generate")

# Default model identifier - can be overridden via environment variable
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "huggingface/distilgpt2")


def _create_model_instance(
    model_id: str,
) -> Union[VLLMModelLoader, LazyModelLoader]:
    """
    Create a model instance based on the configured inference engine.

    Args:
        model_id: Model identifier

    Returns:
        Model instance (VLLMModelLoader or LazyModelLoader)
    """
    if INFERENCE_ENGINE == "vllm":
        try:
            import vllm  # noqa: F401
        except ModuleNotFoundError:
            raise RuntimeError(
                "INFERENCE_ENGINE=vllm but vLLM is not installed. "
                "For local dev without GPU, set INFERENCE_ENGINE=transformers in "
                "apps/polyphemus/.env. For production Docker, vLLM is installed in the image."
            ) from None
        logger.info(f"Creating VLLMModelLoader for: {model_id}")
        return VLLMModelLoader(model_name=model_id, auto_loading=False)
    else:
        logger.info(f"Creating LazyModelLoader (transformers) for: {model_id}")
        return LazyModelLoader(model_name=model_id, auto_loading=False)


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

    # Check vLLM model
    if isinstance(model, VLLMModelLoader):
        return model.vllm_engine is not None

    # Check HuggingFace model (has model/tokenizer attributes)
    if hasattr(model, "model") and hasattr(model, "tokenizer"):
        return model.model is not None and model.tokenizer is not None

    # For other model types, assume loaded if in cache
    return True


async def get_polyphemus_instance(
    model_name: Optional[str] = None,
) -> Union[VLLMModelLoader, LazyModelLoader]:
    """
    Get or create a model instance with lazy async initialization.

    The model is only loaded on first access, not at module import time.
    This prevents blocking application startup and aligns with the design
    intent that models should load on first request.

    Models are cached by model identifier, so subsequent requests for the
    same model will reuse the cached instance.

    Args:
        model_name: Model identifier. If None, uses default model.

    Returns:
        Model instance (VLLMModelLoader or LazyModelLoader)
    """
    model_id = model_name or DEFAULT_MODEL

    # Check if model is already cached (fast path)
    if model_id in _model_cache:
        logger.debug(f"Using cached model instance for: {model_id}")
        return _model_cache[model_id]

    # Model not in cache - need to load it
    async with _model_lock:
        # Double-check: another coroutine might have loaded it
        if model_id in _model_cache:
            logger.debug(f"Model was cached by another coroutine: {model_id}")
            return _model_cache[model_id]

        logger.info(f"Initializing model with {INFERENCE_ENGINE} engine: {model_id} (first time)")

        try:
            model_instance = _create_model_instance(model_id)

            # Load model in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, model_instance.load_model)

            # Cache the model instance
            _model_cache[model_id] = model_instance

            logger.info(
                f"Model instance cached and ready: {model_id}, "
                f"engine: {INFERENCE_ENGINE}, "
                f"cache size: {len(_model_cache)}"
            )
            return _model_cache[model_id]
        except Exception as load_error:
            logger.error(f"Failed to load model '{model_id}': {load_error}")
            if model_id != DEFAULT_MODEL:
                pass  # Exit lock, fall back to default below
            else:
                raise

    # Requested model failed, fall back to default
    if model_id != DEFAULT_MODEL:
        logger.info(f"Falling back to default model: {DEFAULT_MODEL}")
        default_model = await get_polyphemus_instance(model_name=None)
        _model_cache[model_id] = default_model
        return default_model
    else:
        raise RuntimeError(f"Failed to load default model: {DEFAULT_MODEL}")


def _extract_prompt_from_messages(
    messages: List[Message],
) -> tuple[str, Optional[str]]:
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

        if msg.role == "system":
            system_prompt = content
        else:
            prompt_parts.append(content)

    prompt = "\n".join(prompt_parts) if prompt_parts else ""
    return prompt, system_prompt


async def generate_text(request: GenerateRequest) -> Dict:
    """
    Generate text using the configured inference engine.

    This is the main business logic for text generation. It handles:
    - Extracting prompts from messages
    - Loading/getting the model instance (vLLM or transformers)
    - Building generation parameters
    - Executing generation with retry logic
    - Formatting the response

    Args:
        request: GenerateRequest with messages, model, and parameters

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

    # Performance timing
    start_total = time.time()

    # Get model instance (lazy initialization on first access)
    requested_model_name = request.model
    start_model_load = time.time()
    try:
        llm = await get_polyphemus_instance(model_name=requested_model_name)
        model_load_time = time.time() - start_model_load
        logger.info(f"Model load/get time: {model_load_time:.2f}s")

        # Check if fallback occurred
        returned_model_name = getattr(llm, "_model_name", getattr(llm, "model_name", None))
        if requested_model_name and returned_model_name != requested_model_name:
            logger.info(
                f"Model fallback: requested '{requested_model_name}' "
                f"but received '{returned_model_name}'"
            )
            actual_model_name = None
        else:
            actual_model_name = requested_model_name
    except Exception as model_error:
        model_load_time = time.time() - start_model_load
        logger.warning(
            f"Failed to load model '{requested_model_name}', using default: {model_error}"
        )
        llm = await get_polyphemus_instance(model_name=None)
        actual_model_name = None
        logger.info(f"Model load/get time (with fallback): {model_load_time:.2f}s")

    logger.info(
        f"Generating with prompt: {prompt[:100]}..., "
        f"system_prompt: {system_prompt}, max_tokens: {max_tokens}, "
        f"engine: {INFERENCE_ENGINE}"
    )

    # Verify model is loaded
    if isinstance(llm, VLLMModelLoader):
        if llm.vllm_engine is None:
            raise RuntimeError("vLLM engine not loaded. Please check model initialization.")
    elif hasattr(llm, "model") and hasattr(llm, "tokenizer"):
        if llm.model is None or llm.tokenizer is None:
            raise RuntimeError("Model or tokenizer not loaded. Please check model initialization.")

    # Build generation kwargs: use max_new_tokens only (HF rejects max_tokens; vLLM maps it)
    max_new_tokens = max_tokens if max_tokens else 2048
    gen_kwargs = {
        "prompt": prompt,
        "system_prompt": system_prompt,
        "temperature": max(temperature, 0.01),
        "max_new_tokens": max_new_tokens,
        "top_p": top_p,
        "repetition_penalty": repetition_penalty,
    }

    # Add top_k if provided
    if top_k is not None:
        gen_kwargs["top_k"] = top_k

    # Add transformers-specific kwargs only for non-vLLM engines
    if not isinstance(llm, VLLMModelLoader):
        gen_kwargs["do_sample"] = True
        gen_kwargs["min_new_tokens"] = 5
        gen_kwargs["no_repeat_ngram_size"] = 3

    logger.info(
        f"Generation config: max_tokens={max_new_tokens}, "
        f"temperature={temperature}, engine={INFERENCE_ENGINE}"
    )

    # Run blocking generate call in thread pool
    loop = asyncio.get_event_loop()
    start_generation = time.time()
    try:
        response = await loop.run_in_executor(
            _executor,
            lambda: llm.generate(**gen_kwargs),
        )
        generation_time = time.time() - start_generation
        logger.info(f"Generation time: {generation_time:.2f}s")
    except Exception as gen_error:
        generation_time = time.time() - start_generation
        logger.error(f"Generation error: {gen_error}", exc_info=True)
        logger.info(f"Generation time (failed): {generation_time:.2f}s")
        raise RuntimeError(f"Generation failed: {gen_error}")

    # Log response details
    response_length = len(response) if isinstance(response, str) else 0
    logger.info(
        f"Generated response type: {type(response)}, "
        f"length: {response_length}, "
        f"content: {repr(response[:200]) if response else 'None'}"
    )

    # Calculate total request time
    total_time = time.time() - start_total
    logger.info(f"Total request time: {total_time:.2f}s")

    # Handle empty responses with retry
    if not response or (isinstance(response, str) and not response.strip()):
        logger.warning(
            f"Empty response from model. Prompt: {prompt[:50]}..., Response: {repr(response)}"
        )
        try:
            logger.info("Retrying generation with adjusted parameters...")
            retry_kwargs = {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": 0.9,
                "max_new_tokens": max(max_tokens, 50),
                "top_p": 0.95,
                "top_k": 50,
                "repetition_penalty": max(repetition_penalty, 1.3),
            }
            if not isinstance(llm, VLLMModelLoader):
                retry_kwargs["do_sample"] = True
                retry_kwargs["min_new_tokens"] = 10
                retry_kwargs["no_repeat_ngram_size"] = 4

            response = await loop.run_in_executor(
                _executor,
                lambda: llm.generate(**retry_kwargs),
            )
            logger.info(f"Retry response: {repr(response[:100]) if response else 'None'}")
        except Exception as retry_error:
            logger.error(f"Retry generation also failed: {retry_error}")
            response = None

        if not response or (isinstance(response, str) and not response.strip()):
            logger.error("Model returned empty response even after retry")
            response = (
                "I'm sorry, I couldn't generate a response. The model returned an empty output."
            )
    elif isinstance(response, str):
        response = response.strip()
    else:
        response = str(response).strip()

    # Determine response model name
    if actual_model_name:
        response_model_name = actual_model_name
    else:
        response_model_name = DEFAULT_MODEL

    logger.info(f"Response using model: {response_model_name}")

    # Calculate token counts (word-based approximation)
    prompt_tokens = len(prompt.split()) if prompt else 0
    completion_tokens = len(response.split()) if response else 0

    # Return Rhesis API format
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": response,
                },
                "finish_reason": "stop",
            }
        ],
        "model": response_model_name,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }

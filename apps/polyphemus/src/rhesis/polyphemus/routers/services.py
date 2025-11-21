"""
Rhesis API endpoints for Polyphemus service.
Provides /generate endpoint that accepts messages format.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from ..schemas import GenerateRequest, Message
from ..services import get_polyphemus_instance

# Thread pool executor for running blocking operations
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="polyphemus-generate")

logger = logging.getLogger("rhesis-polyphemus")

router = APIRouter()


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


@router.post("/generate")
async def generate(request: GenerateRequest):
    """
    Generate text using Rhesis API format.

    Accepts:
        {
            "messages": [
                { "content": "Hello!", "role": "user" }
            ],
            "temperature": 0.7,
            "max_tokens": 512,
            "model": "huggingface/distilgpt2"  # optional
        }

    Returns:
        Rhesis API response format
    """
    try:
        # Extract prompt and system prompt from messages
        prompt, system_prompt = _extract_prompt_from_messages(request.messages)

        if not prompt:
            raise HTTPException(
                status_code=400, detail="At least one message with content is required"
            )

        # Get generation parameters
        temperature = request.temperature or 0.7
        max_tokens = request.max_tokens or 512
        # Default repetition_penalty to 1.2 to prevent repetition loops
        # Higher values = stronger penalty against repetition
        repetition_penalty = (
            request.repetition_penalty if request.repetition_penalty is not None else 1.2
        )
        top_p = request.top_p if request.top_p is not None else 0.9
        top_k = request.top_k

        # Get model instance based on request (lazy initialization on first access)
        # Use model from request if provided, otherwise use default
        # If model name is invalid, fall back to default
        model_name = request.model
        try:
            llm = await get_polyphemus_instance(model_name=model_name)
        except Exception as model_error:
            logger.warning(
                f"Failed to load model '{model_name}', using default: {str(model_error)}"
            )
            llm = await get_polyphemus_instance(model_name=None)

        # Run the blocking generate call in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()

        logger.info(
            f"Generating with prompt: {prompt[:100]}..., "
            f"system_prompt: {system_prompt}, max_tokens: {max_tokens}"
        )

        # Check if model is loaded before generating (for HuggingFace models)
        if hasattr(llm, "model") and hasattr(llm, "tokenizer"):
            if llm.model is None or llm.tokenizer is None:
                logger.error("Model or tokenizer not loaded!")
                raise HTTPException(
                    status_code=500, detail="Model not loaded. Please check model initialization."
                )

        # Generate with proper parameters to ensure output
        # Note: pad_token_id and eos_token_id are set by the SDK automatically
        try:
            # Build generation kwargs
            gen_kwargs = {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": max(temperature, 0.7),  # Ensure minimum temperature
                "max_new_tokens": max(max_tokens, 20),  # Ensure minimum tokens
                "min_new_tokens": 5,  # Force at least 5 new tokens
                "do_sample": True,  # Enable sampling (required for temperature)
                "top_p": top_p,  # Nucleus sampling
                "repetition_penalty": repetition_penalty,  # Penalize repetition
                "no_repeat_ngram_size": 3,  # Prevent repeating 3-grams
            }

            # Add top_k if provided
            if top_k is not None:
                gen_kwargs["top_k"] = top_k

            response = await loop.run_in_executor(
                _executor,
                lambda: llm.generate(**gen_kwargs),
            )
        except Exception as gen_error:
            logger.error(f"Generation error: {str(gen_error)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Generation failed: {str(gen_error)}")

        logger.info(
            f"Generated response type: {type(response)}, "
            f"length: {len(response) if response else 0}, "
            f"content: {repr(response[:200]) if response else 'None'}"
        )

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

        # Get model name from instance
        model_name = getattr(llm, "model_name", "polyphemus")

        # Calculate token counts (simple word-based approximation)
        prompt_tokens = len(prompt.split()) if prompt else 0
        completion_tokens = len(response.split()) if response else 0

        # Return Rhesis API format
        return {
            "choices": [
                {"message": {"role": "assistant", "content": response}, "finish_reason": "stop"}
            ],
            "model": model_name,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

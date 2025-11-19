"""
Inference module using HuggingFaceLLM from the SDK.
This replaces the previous InferenceEngine with SDK-based implementation.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Dict, Optional

from rhesis.sdk.models import HuggingFaceLLM

logger = logging.getLogger("rhesis-polyphemus")

# Model name - can be overridden via environment variable
modelname = "distilgpt2"


def format_prompt(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Format the prompt for models.
    Note: HuggingFaceLLM handles prompt formatting internally,
    but this function is kept for compatibility.
    """
    if system_prompt:
        return f"{system_prompt}\n\n{prompt}"
    return prompt


class InferenceEngine:
    """
    Inference engine using HuggingFaceLLM from the SDK.
    Uses a singleton pattern to avoid reloading the model on every request.
    """

    _llm_instance = None
    _model_name = None
    _executor = None  # Thread pool executor for running blocking operations

    def __init__(self, model=None, tokenizer=None):
        """
        Initialize the inference engine.
        For compatibility, model and tokenizer parameters are accepted but ignored.
        The actual model is loaded via HuggingFaceLLM (singleton pattern).
        """
        # Get model name from environment or use default
        import os

        self.model_name = os.environ.get("HF_MODEL", modelname)

        # Use singleton pattern - only load model once
        if InferenceEngine._llm_instance is None or InferenceEngine._model_name != self.model_name:
            logger.info(f"Loading HuggingFaceLLM model: {self.model_name}")
            InferenceEngine._llm_instance = HuggingFaceLLM(self.model_name)

            # Fix pad_token for GPT-2 models if needed
            if InferenceEngine._llm_instance.tokenizer.pad_token is None:
                InferenceEngine._llm_instance.tokenizer.pad_token = (
                    InferenceEngine._llm_instance.tokenizer.eos_token
                )

            InferenceEngine._model_name = self.model_name
            logger.info(f"Model loaded successfully: {self.model_name}")
        else:
            logger.debug(f"Reusing existing model instance: {self.model_name}")

        # Use the singleton instance
        self.llm = InferenceEngine._llm_instance

        # Initialize thread pool executor for running blocking operations
        if InferenceEngine._executor is None:
            InferenceEngine._executor = ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="inference"
            )

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        system_prompt: Optional[str] = None,
    ) -> Dict:
        """Generate text (non-streaming) using HuggingFaceLLM"""
        try:
            # Use the SDK's generate method
            # Map parameters to SDK format
            kwargs = {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "repetition_penalty": repetition_penalty,
            }

            # Run the blocking generate call in a thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                InferenceEngine._executor,
                lambda: self.llm.generate(prompt=prompt, system_prompt=system_prompt, **kwargs),
            )

            # Get metadata if available
            metadata = getattr(self.llm, "last_generation_metadata", {})
            generation_time = metadata.get("generation_time_seconds", 0.0)
            output_tokens = metadata.get("output_tokens", len(response.split()))

            logger.info(f"Generation completed in {generation_time:.2f} seconds")

            return {
                "generated_text": response.strip(),
                "tokens_generated": output_tokens,
                "generation_time_seconds": generation_time,
            }
        except Exception as e:
            logger.error(f"Error during generation: {str(e)}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response.
        Note: HuggingFaceLLM doesn't natively support token-by-token streaming, so we
        run the blocking generation in a thread pool executor and then simulate streaming
        by yielding word chunks to avoid blocking the event loop.
        """
        try:
            # Prepare generation parameters
            kwargs = {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "repetition_penalty": repetition_penalty,
            }

            # Run the blocking generate call in a thread pool to avoid blocking the event loop
            # This allows the async event loop to handle other requests concurrently
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                InferenceEngine._executor,
                lambda: self.llm.generate(prompt=prompt, system_prompt=system_prompt, **kwargs),
            )

            # Simulate streaming by yielding words as chunks
            # This provides a better user experience than waiting for the full response
            words = response.split()
            for word in words:
                yield f"data: {word}\n\n"
                # Small yield to allow other coroutines to run
                await asyncio.sleep(0)

            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error during streaming generation: {str(e)}")
            yield f"data: Error: {str(e)}\n\n"

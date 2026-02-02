"""
Model implementations for Polyphemus service.
Contains different model classes that can be used based on configuration.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Union

from rhesis.sdk.models import BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger("rhesis-polyphemus")

# Default model for LazyModelLoader - can be overridden via environment variable
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "huggingface/distilgpt2")

# Model path configuration - supports local path or GCS bucket location
# For GCS paths, the bucket should be mounted at /gcs-models via Cloud Run volume mount
MODEL_PATH = os.environ.get("MODEL_PATH", "")

# GCS volume mount path (Cloud Run mounts GCS bucket here)
GCS_MOUNT_PATH = "/gcs-models"


def _map_gcs_to_mounted_path(model_name: str, gcs_path: str) -> str:
    """
    Map GCS path to mounted volume path for Cloud Run.

    Cloud Run mounts GCS buckets at /gcs-models, so we convert:
    gs://bucket/path/to/model -> /gcs-models/path/to/model

    Args:
        model_name: Model identifier (e.g., "organization/model-name")
        gcs_path: GCS path (e.g., "gs://bucket-name/models")

    Returns:
        str: Local mounted path (e.g., "/gcs-models/models/model-name")
    """
    if not gcs_path.startswith("gs://"):
        return gcs_path

    # Parse GCS path: gs://bucket/path -> bucket, path
    bucket_and_path = gcs_path[5:]  # Remove "gs://"
    parts = bucket_and_path.split("/", 1)
    bucket_path = parts[1] if len(parts) > 1 else ""

    # Get model directory name from model_name
    model_dir_name = model_name.split("/")[-1]

    # Construct mounted path
    if bucket_path:
        mounted_path = f"{GCS_MOUNT_PATH}/{bucket_path}/{model_dir_name}"
    else:
        mounted_path = f"{GCS_MOUNT_PATH}/{model_dir_name}"

    logger.info(f"Mapped GCS path: {gcs_path}/{model_dir_name}")
    logger.info(f"To mounted path: {mounted_path}")

    return mounted_path


class LazyModelLoader(BaseLLM):
    """
    LazyModelLoader model class that can load any LLM model based on user requirements.

    This is a flexible model wrapper that uses the SDK's get_model factory
    to load any supported model type (HuggingFace, OpenAI, Anthropic, etc.)
    based on the model name/type provided.

    The model name can be specified in the format:
    - "provider/model-name" (e.g., "huggingface/distilgpt2", "openai/gpt-4o")
    - "model-name" (defaults to huggingface provider)
    """

    def __init__(self, model_name: Optional[str] = None, auto_loading: bool = True):
        """
        Initialize LazyModelLoader model.

        Args:
            model_name: Model identifier in format "provider/model" or just model name.
                If None, uses default model (huggingface/distilgpt2).
            auto_loading: Whether to automatically load the model on initialization.
                If False, model loading is deferred until load_model() is called.
        """
        # Use default model if not provided
        self._model_name = model_name or DEFAULT_MODEL
        self._auto_loading = auto_loading
        self._internal_model: Optional[BaseLLM] = None

        # Set model_name for BaseLLM compatibility (don't call super().__init__
        # as it would trigger load_model immediately)
        self.model_name = self._model_name
        self.model = None
        self.tokenizer = None

        if auto_loading:
            self.load_model()

    def load_model(self) -> BaseLLM:
        """
        Load the model using the SDK's get_model factory.

        If MODEL_PATH is configured:
        - For GCS paths (gs://...): maps to mounted volume at /gcs-models
        - For local paths: loads from local disk
        - If not set: uses HuggingFace Hub to download

        The model can be any supported type (HuggingFace, OpenAI, etc.)
        based on the model_name format.

        Returns:
            self: Returns self for method chaining
        """
        if self._internal_model is None:
            logger.info(f"Loading model: {self._model_name}")

            # Determine the model source to use (local path or Hub identifier)
            model_source = None
            if MODEL_PATH:
                # Check if it's a GCS path and map to mounted volume
                if MODEL_PATH.startswith("gs://"):
                    model_source = _map_gcs_to_mounted_path(self._model_name, MODEL_PATH)
                    logger.info(f"Using Cloud Storage mounted volume at: {model_source}")
                else:
                    # Use local path directly
                    model_source = MODEL_PATH
                    logger.info(f"Using local path: {model_source}")
            else:
                # No MODEL_PATH set - will download from HuggingFace Hub
                logger.info("No MODEL_PATH set, will use HuggingFace Hub")

            # Configure load_kwargs for optimal GPU performance
            # Use FP16 for best performance on L4 GPU
            # Enable caching and optimizations
            # Note: device_map is handled automatically by HuggingFace SDK, don't set it here
            import torch

            default_load_kwargs = {
                "torch_dtype": torch.float16,  # FP16 for faster inference on GPU
                "use_cache": True,  # Enable KV-cache for faster generation
                "low_cpu_mem_usage": True,  # Optimize CPU memory during loading
            }

            # Allow override via environment variable for advanced configurations
            # Support both base64-encoded (LOAD_KWARGS_B64) and plain JSON (LOAD_KWARGS)
            # Examples:
            # - 8-bit: LOAD_KWARGS='{"load_in_8bit": true}'
            # - 4-bit: LOAD_KWARGS='{"load_in_4bit": true}'
            # - FP16: LOAD_KWARGS='{"torch_dtype":"float16","use_cache":true}'
            load_kwargs_env = os.environ.get("LOAD_KWARGS_B64") or os.environ.get("LOAD_KWARGS")
            if load_kwargs_env:
                import base64
                import json

                try:
                    # If it's base64-encoded, decode it first
                    if os.environ.get("LOAD_KWARGS_B64"):
                        load_kwargs_json = base64.b64decode(load_kwargs_env).decode("utf-8")
                        logger.info("Decoding LOAD_KWARGS from base64")
                    else:
                        load_kwargs_json = load_kwargs_env

                    parsed_kwargs = json.loads(load_kwargs_json)

                    # Handle torch_dtype string conversion
                    if "torch_dtype" in parsed_kwargs:
                        dtype_str = parsed_kwargs["torch_dtype"]
                        if isinstance(dtype_str, str):
                            if dtype_str == "float16" or dtype_str == "fp16":
                                parsed_kwargs["torch_dtype"] = torch.float16
                            elif dtype_str == "float32" or dtype_str == "fp32":
                                parsed_kwargs["torch_dtype"] = torch.float32
                            elif dtype_str == "bfloat16" or dtype_str == "bf16":
                                parsed_kwargs["torch_dtype"] = torch.bfloat16

                    # Merge with defaults, allowing override
                    default_load_kwargs.update(parsed_kwargs)
                    logger.info(f"Using custom load_kwargs from env: {default_load_kwargs}")
                except (json.JSONDecodeError, base64.binascii.Error) as e:
                    logger.warning(
                        f"Invalid LOAD_KWARGS (error: {e}), using default: {default_load_kwargs}"
                    )

            logger.info(f"Loading with configuration: {default_load_kwargs}")

            try:
                self._internal_model = get_model(
                    self._model_name,
                    auto_loading=False,
                    model_path=model_source,
                    load_kwargs=default_load_kwargs,
                )
            except TypeError:
                # If model_path is not supported by this model type, try without it
                logger.info("model_path not supported for this model type, creating without it")
                self._internal_model = get_model(self._model_name, auto_loading=False)

            # Load the model (for HuggingFace models, this loads model and tokenizer)
            if hasattr(self._internal_model, "load_model"):
                self._internal_model.load_model()

            # Set model attribute for compatibility
            if hasattr(self._internal_model, "model"):
                self.model = self._internal_model.model
            if hasattr(self._internal_model, "tokenizer"):
                self.tokenizer = self._internal_model.tokenizer

            # Try to optimize with BetterTransformer (PyTorch 2.0+ optimization)
            # This can provide 1.5-2x speedup for inference
            # Requires: pip install optimum
            if hasattr(self._internal_model, "model") and hasattr(
                self._internal_model.model, "to_bettertransformer"
            ):
                try:
                    logger.info("Applying BetterTransformer optimization...")
                    self._internal_model.model = self._internal_model.model.to_bettertransformer()
                    self.model = self._internal_model.model
                    logger.info("✅ BetterTransformer applied successfully (1.5-2x speedup)")
                except ImportError as import_error:
                    logger.info(
                        f"⚠️ BetterTransformer not available (optional): {import_error}. "
                        f"Install 'optimum' package for 1.5-2x inference speedup."
                    )
                except Exception as bt_error:
                    logger.warning(
                        f"BetterTransformer optimization failed: {bt_error}. "
                        f"Continuing without optimization."
                    )

            # GPU monitoring: Verify model is on GPU and log memory usage
            if hasattr(self._internal_model, "model"):
                try:
                    import torch

                    if torch.cuda.is_available():
                        # Check device of model parameters
                        first_param = next(self._internal_model.model.parameters(), None)
                        if first_param is not None:
                            device = first_param.device
                            logger.info(f"✅ Model on device: {device}")

                            # Log GPU memory usage
                            allocated_gb = torch.cuda.memory_allocated() / 1e9
                            reserved_gb = torch.cuda.memory_reserved() / 1e9
                            logger.info(
                                f"✅ GPU Memory - Allocated: {allocated_gb:.2f}GB, "
                                f"Reserved: {reserved_gb:.2f}GB"
                            )

                            # Log GPU name
                            gpu_name = torch.cuda.get_device_name(0)
                            logger.info(f"✅ GPU: {gpu_name}")
                        else:
                            logger.warning("⚠️ Model has no parameters to check device")
                    else:
                        logger.warning("⚠️ CUDA not available - model may be on CPU!")
                except Exception as gpu_error:
                    logger.warning(f"Could not check GPU status: {gpu_error}")

            logger.info(f"Model loaded successfully: {self._model_name}")

        return self

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Any] = None,
        **kwargs,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate a response using the loaded model.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Optional schema for structured output
            **kwargs: Additional generation parameters

        Returns:
            str or dict: Generated response
        """
        if self._internal_model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Delegate to the internal model
        return self._internal_model.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            schema=schema,
            **kwargs,
        )

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Any] = None,
        **kwargs,
    ) -> List[Union[str, Dict[str, Any]]]:
        """
        Generate responses for multiple prompts using the loaded model.

        Falls back to sequential generation if batch processing is not supported
        by the underlying provider (e.g., lmformatenforcer, huggingface).

        Args:
            prompts: List of user prompts
            system_prompt: Optional system prompt (applied to all prompts)
            schema: Optional schema for structured output
            **kwargs: Additional generation parameters

        Returns:
            List of str or dict: Generated responses
        """
        if self._internal_model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        try:
            # Try batch processing first (works for API-based providers)
            return self._internal_model.generate_batch(
                prompts=prompts,
                system_prompt=system_prompt,
                schema=schema,
                **kwargs,
            )
        except NotImplementedError:
            # Fallback to sequential generation for providers that don't support batch
            logger.info(
                f"Batch processing not supported by {self._model_name}, "
                f"falling back to sequential generation"
            )
            results = []
            for prompt in prompts:
                result = self._internal_model.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    schema=schema,
                    **kwargs,
                )
                results.append(result)
            return results

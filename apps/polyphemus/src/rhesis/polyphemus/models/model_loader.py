"""
Model implementations for Polyphemus service.
Contains different model classes that can be used based on configuration.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from rhesis.sdk.models import BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger("rhesis-polyphemus")

# Default model for LazyModelLoader - can be overridden via environment variable
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "huggingface/distilgpt2")

# Model path configuration - supports local path or GCS bucket location
MODEL_PATH = os.environ.get("MODEL_PATH", "")


def _download_from_gcs_if_needed(model_name: str, gcs_path: str) -> str:
    """
    Download model from GCS bucket to local cache if MODEL_PATH is a GCS location.

    Args:
        model_name: Model identifier (e.g., "NousResearch/DeepHermes-3-Llama-3-3B-Preview")
        gcs_path: GCS path (e.g., "gs://bucket/path")

    Returns:
        str: Local path where model is cached

    Raises:
        ImportError: If google-cloud-storage is not installed
        RuntimeError: If download fails
    """
    if not gcs_path.startswith("gs://"):
        return gcs_path

    try:
        from google.cloud import storage
    except ImportError:
        logger.error("google-cloud-storage is required for GCS model loading")
        logger.error("Install it with: pip install google-cloud-storage")
        raise ImportError(
            "google-cloud-storage is required for GCS model loading. "
            "Install with: pip install google-cloud-storage"
        )

    # Parse GCS path
    bucket_name = gcs_path[5:].split("/")[0]
    bucket_prefix = "/".join(gcs_path[5:].split("/")[1:])
    model_dir_name = model_name.split("/")[-1]

    # Local cache directory
    local_cache_dir = Path("/app/models") / model_dir_name
    local_cache_dir.mkdir(parents=True, exist_ok=True)

    # Check if model already cached
    if list(local_cache_dir.glob("*.safetensors")) or list(local_cache_dir.glob("*.bin")):
        logger.info(f"Model already cached at: {local_cache_dir}")
        return str(local_cache_dir)

    logger.info(f"Downloading model from GCS: {gcs_path}/{model_dir_name}")
    logger.info(f"Local cache directory: {local_cache_dir}")

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        # List all blobs in the GCS path
        gcs_model_prefix = f"{bucket_prefix}/{model_dir_name}" if bucket_prefix else model_dir_name
        blobs = bucket.list_blobs(prefix=gcs_model_prefix)

        blob_count = 0
        for blob in blobs:
            # Extract relative path from GCS
            relative_path = blob.name[len(gcs_model_prefix) :].lstrip("/")
            if not relative_path:
                continue

            local_file = local_cache_dir / relative_path
            local_file.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading: {blob.name} -> {local_file}")
            blob.download_to_filename(local_file)
            blob_count += 1

        if blob_count == 0:
            raise RuntimeError(
                f"No model files found in GCS path: gs://{bucket_name}/{gcs_model_prefix}"
            )

        logger.info(f"Downloaded {blob_count} files from GCS to {local_cache_dir}")
        return str(local_cache_dir)

    except Exception as e:
        logger.error(f"Failed to download model from GCS: {str(e)}")
        raise RuntimeError(f"GCS download failed: {str(e)}")


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
        - For local paths: loads from local disk
        - For GCS paths (gs://...): downloads from GCS to local cache first, then loads
        - Uses /app/models/{model_name} as default path if MODEL_PATH not set

        The model can be any supported type (HuggingFace, OpenAI, etc.)
        based on the model_name format.

        Returns:
            self: Returns self for method chaining
        """
        if self._internal_model is None:
            logger.info(f"Loading model: {self._model_name}")

            # Determine the model path to use
            model_path = None
            if MODEL_PATH:
                # Check if it's a GCS path and download if needed
                if MODEL_PATH.startswith("gs://"):
                    model_path = _download_from_gcs_if_needed(self._model_name, MODEL_PATH)
                else:
                    # Use local path directly
                    model_path = MODEL_PATH
            else:
                # Use default local cache path
                model_name_dir = self._model_name.split("/")[-1]
                model_path = f"/app/models/{model_name_dir}"

            logger.info(f"Model path: {model_path}")

            # Use SDK's get_model factory to create the appropriate model
            # Pass auto_loading=False and model_path via kwargs
            try:
                self._internal_model = get_model(
                    self._model_name,
                    auto_loading=False,
                    model_path=model_path,
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

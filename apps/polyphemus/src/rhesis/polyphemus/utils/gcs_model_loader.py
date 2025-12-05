"""
GCS Model Loader - Downloads models from Google Cloud Storage.

This module provides functionality to download pre-cached models from GCS
to local storage at application startup. This is much faster than downloading
from HuggingFace Hub directly (2-5 min vs 40+ min).
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("rhesis-polyphemus")


def download_model_from_gcs(
    model_name: str,
    model_bucket: str,
    local_cache_dir: str = "/app/model_cache",
    force_download: bool = False,
) -> bool:
    """
    Download model from GCS to local cache directory.

    Args:
        model_name: Full model name (e.g., "huggingface/org/model-name")
        model_bucket: GCS bucket name containing the model
        local_cache_dir: Local directory to cache the model
        force_download: Force re-download even if model exists locally

    Returns:
        bool: True if download succeeded or model already exists, False otherwise

    Raises:
        Exception: If GCS download fails
    """
    try:
        from google.cloud import storage
    except ImportError:
        logger.error("google-cloud-storage not installed. Cannot download from GCS.")
        return False

    # Check if model already exists locally (warm start optimization)
    local_cache_path = Path(local_cache_dir)
    if not force_download and local_cache_path.exists():
        # Check if directory has model files (safetensors or bin files)
        model_files = list(local_cache_path.rglob("*.safetensors")) + list(
            local_cache_path.rglob("*.bin")
        )
        if model_files:
            logger.info(
                f"Model already cached locally at {local_cache_dir} ({len(model_files)} files)"
            )
            return True

    # Extract clean model name and create GCS path
    model_name_clean = model_name.replace("huggingface/", "")
    # Sanitize for GCS path (replace / with -)
    model_path = f"models/{model_name_clean.replace('/', '-')}"

    # HuggingFace expects models in a specific cache structure:
    # <cache_dir>/models--<org>--<model>/snapshots/main/
    # Convert "NousResearch/Model" -> "models--NousResearch--Model"
    hf_model_dir = f"models--{model_name_clean.replace('/', '--')}"
    hf_cache_path = local_cache_path / hf_model_dir / "snapshots" / "main"

    logger.info(f"📥 Downloading model from GCS: gs://{model_bucket}/{model_path}/")
    logger.info(f"📂 Destination: {hf_cache_path}")
    logger.info("⏱️  This may take 2-5 minutes (fast internal GCP transfer)...")

    try:
        # Initialize GCS client
        storage_client = storage.Client()
        bucket = storage_client.bucket(model_bucket)

        # Create HuggingFace cache directory structure
        hf_cache_path.mkdir(parents=True, exist_ok=True)

        # List all blobs in the model path
        blobs = list(bucket.list_blobs(prefix=model_path))

        if not blobs:
            logger.error(
                f"No files found in gs://{model_bucket}/{model_path}/. "
                f"Please run the 'Upload Model to GCS' workflow first."
            )
            return False

        logger.info(f"Found {len(blobs)} files to download")

        # Download each blob
        downloaded_count = 0
        for i, blob in enumerate(blobs, 1):
            # Skip directory markers
            if blob.name.endswith("/"):
                continue

            # Create local file path (remove model_path prefix)
            relative_path = blob.name.replace(f"{model_path}/", "")
            local_file = hf_cache_path / relative_path

            # Create parent directories
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # Download the file
            logger.debug(f"Downloading [{i}/{len(blobs)}]: {blob.name}")
            blob.download_to_filename(str(local_file))
            downloaded_count += 1

            # Log progress every 10 files
            if downloaded_count % 10 == 0:
                logger.info(f"Downloaded {downloaded_count}/{len(blobs)} files...")

        logger.info(
            f"✅ Model downloaded successfully! ({downloaded_count} files to {hf_cache_path})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to download model from GCS: {e}")
        logger.error(
            f"Please ensure: 1) Model exists at gs://{model_bucket}/{model_path}/, "
            f"2) Service account has Storage Object Viewer permissions, "
            f"3) MODEL_BUCKET environment variable is correct"
        )
        return False


def ensure_model_cached(
    model_name: Optional[str] = None,
    model_bucket: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> bool:
    """
    Ensure model is cached locally, downloading from GCS if needed.

    This function should be called at application startup to ensure the model
    is available before serving requests.

    Args:
        model_name: Model name (defaults to DEFAULT_MODEL env var)
        model_bucket: GCS bucket name (defaults to MODEL_BUCKET env var)
        cache_dir: Local cache directory (defaults to TRANSFORMERS_CACHE env var)

    Returns:
        bool: True if model is cached and ready, False otherwise
    """
    # Get configuration from environment variables
    model_name = model_name or os.environ.get("DEFAULT_MODEL")
    model_bucket = model_bucket or os.environ.get("MODEL_BUCKET")
    cache_dir = cache_dir or os.environ.get("TRANSFORMERS_CACHE", "/app/model_cache")

    if not model_name:
        logger.warning("DEFAULT_MODEL not set, skipping GCS model download")
        return False

    if not model_bucket:
        logger.warning(
            "MODEL_BUCKET not set, skipping GCS model download. "
            "Model will be downloaded from HuggingFace at runtime (slow)."
        )
        return False

    logger.info(f"Ensuring model is cached: {model_name}")

    return download_model_from_gcs(
        model_name=model_name,
        model_bucket=model_bucket,
        local_cache_dir=cache_dir,
        force_download=False,
    )

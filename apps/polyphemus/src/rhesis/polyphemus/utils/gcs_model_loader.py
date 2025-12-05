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
    logger.info("=" * 80)
    logger.info("GCS MODEL DOWNLOAD STARTING")
    logger.info("=" * 80)
    logger.info("Function called with:")
    logger.info(f"  model_name: {model_name}")
    logger.info(f"  model_bucket: {model_bucket}")
    logger.info(f"  local_cache_dir: {local_cache_dir}")
    logger.info(f"  force_download: {force_download}")

    try:
        logger.info("Importing google.cloud.storage...")
        from google.cloud import storage

        logger.info("google.cloud.storage imported successfully")
    except ImportError as import_error:
        logger.error("=" * 80)
        logger.error("IMPORT ERROR")
        logger.error("=" * 80)
        logger.error(f"Failed to import google.cloud.storage: {import_error}")
        logger.error("Please install: pip install google-cloud-storage")
        logger.error("=" * 80)
        return False

    # Check if model already exists locally (warm start optimization)
    local_cache_path = Path(local_cache_dir)
    logger.info(f"Checking local cache directory: {local_cache_path}")
    logger.info(f"Local cache exists: {local_cache_path.exists()}")
    logger.info(f"Force download: {force_download}")

    if not force_download and local_cache_path.exists():
        # Check if directory has model files (safetensors or bin files)
        logger.info("Scanning for existing model files...")
        safetensors_files = list(local_cache_path.rglob("*.safetensors"))
        bin_files = list(local_cache_path.rglob("*.bin"))
        model_files = safetensors_files + bin_files

        logger.info(f"Found {len(safetensors_files)} .safetensors files")
        logger.info(f"Found {len(bin_files)} .bin files")
        logger.info(f"Total model files found: {len(model_files)}")

        if model_files:
            # Log first few file paths for debugging
            sample_files = model_files[:5]
            logger.info("Sample model files found:")
            for f in sample_files:
                logger.info(f"  - {f}")
            logger.info(
                f"Model already cached locally at {local_cache_dir} ({len(model_files)} files)"
            )
            return True
        else:
            logger.info("No model files found in local cache, proceeding with download")

    # Extract clean model name and create GCS path
    logger.info(f"Processing model name: {model_name}")
    model_name_clean = model_name.replace("huggingface/", "")
    logger.info(f"Cleaned model name: {model_name_clean}")

    # Sanitize for GCS path (replace / with -)
    model_path = f"models/{model_name_clean.replace('/', '-')}"
    logger.info(f"GCS bucket path: gs://{model_bucket}/{model_path}/")

    # HuggingFace expects models in a specific cache structure:
    # <cache_dir>/models--<org>--<model>/snapshots/main/
    # Convert "NousResearch/Model" -> "models--NousResearch--Model"
    hf_model_dir = f"models--{model_name_clean.replace('/', '--')}"
    hf_cache_path = local_cache_path / hf_model_dir / "snapshots" / "main"

    logger.info(f"HuggingFace model directory: {hf_model_dir}")
    logger.info(f"Full HuggingFace cache path: {hf_cache_path}")

    logger.info(f"📥 Downloading model from GCS: gs://{model_bucket}/{model_path}/")
    logger.info(f"📂 Destination: {hf_cache_path}")
    logger.info("⏱️  This may take 2-5 minutes (fast internal GCP transfer)...")

    try:
        # Initialize GCS client
        logger.info("Initializing GCS storage client...")
        storage_client = storage.Client()
        logger.info("GCS client initialized successfully")

        logger.info(f"Accessing bucket: {model_bucket}")
        bucket = storage_client.bucket(model_bucket)
        logger.info(f"Bucket object created: {bucket.name}")

        # Create HuggingFace cache directory structure
        logger.info(f"Creating local cache directory: {hf_cache_path}")
        hf_cache_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local cache directory created/verified: {hf_cache_path.exists()}")

        # List all blobs in the model path
        logger.info(f"Listing blobs with prefix: {model_path}")
        logger.info(f"Full GCS path: gs://{model_bucket}/{model_path}/")
        blobs = list(bucket.list_blobs(prefix=model_path))
        logger.info(f"Blob listing completed. Found {len(blobs)} items")

        if not blobs:
            logger.error(
                f"No files found in gs://{model_bucket}/{model_path}/. "
                f"Please run the 'Upload Model to GCS' workflow first."
            )
            # Try to list what's actually in the bucket for debugging
            logger.info("Attempting to list top-level 'models/' directory for debugging...")
            try:
                top_level_blobs = list(bucket.list_blobs(prefix="models/", max_results=20))
                logger.info(f"Found {len(top_level_blobs)} items under 'models/' prefix:")
                for blob in top_level_blobs[:10]:
                    logger.info(f"  - {blob.name}")
            except Exception as debug_error:
                logger.warning(f"Could not list bucket contents for debugging: {debug_error}")
            return False

        # Log details about found blobs
        logger.info(f"Found {len(blobs)} files to download")
        logger.info("Sample blob names:")
        for i, blob in enumerate(blobs[:10], 1):
            logger.info(f"  [{i}] {blob.name} (size: {blob.size} bytes)")
        if len(blobs) > 10:
            logger.info(f"  ... and {len(blobs) - 10} more files")

        # Download each blob
        downloaded_count = 0
        skipped_count = 0
        logger.info("Starting file downloads...")

        for i, blob in enumerate(blobs, 1):
            # Skip directory markers
            if blob.name.endswith("/"):
                skipped_count += 1
                logger.debug(f"Skipping directory marker [{i}/{len(blobs)}]: {blob.name}")
                continue

            # Create local file path (remove model_path prefix)
            relative_path = blob.name.replace(f"{model_path}/", "")
            local_file = hf_cache_path / relative_path

            logger.debug(f"Processing [{i}/{len(blobs)}]: GCS: {blob.name} -> Local: {local_file}")

            # Create parent directories
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # Download the file
            try:
                logger.debug(f"Downloading [{i}/{len(blobs)}]: {blob.name} ({blob.size} bytes)")
                blob.download_to_filename(str(local_file))

                # Verify file was downloaded
                if local_file.exists():
                    actual_size = local_file.stat().st_size
                    logger.debug(
                        f"Downloaded [{i}/{len(blobs)}]: {local_file.name} "
                        f"({actual_size} bytes, expected {blob.size})"
                    )
                    if actual_size != blob.size:
                        logger.warning(
                            f"Size mismatch for {local_file.name}: "
                            f"expected {blob.size}, got {actual_size}"
                        )
                else:
                    logger.error(
                        f"File download failed: {local_file} does not exist after download"
                    )

                downloaded_count += 1
            except Exception as download_error:
                logger.error(f"Failed to download [{i}/{len(blobs)}] {blob.name}: {download_error}")
                raise

            # Log progress every 10 files
            if downloaded_count % 10 == 0:
                logger.info(f"Downloaded {downloaded_count}/{len(blobs)} files...")

        logger.info(
            f"Download complete: {downloaded_count} files downloaded, {skipped_count} skipped"
        )

        # Create HuggingFace cache metadata files
        # HuggingFace looks for refs/main file to know which snapshot to use
        refs_dir = local_cache_path / hf_model_dir / "refs"
        refs_dir.mkdir(parents=True, exist_ok=True)
        refs_main_file = refs_dir / "main"

        # Write "main" as the revision reference
        refs_main_file.write_text("main")
        logger.debug(f"Created refs/main file: {refs_main_file}")

        # Create a .gitattributes file to mark this as a git-lfs repo (optional but helps)
        gitattributes_file = hf_cache_path / ".gitattributes"
        gitattributes_file.write_text("*.safetensors filter=lfs diff=lfs merge=lfs -text\n")

        # Set an environment variable to signal that model is cached locally
        os.environ["RHESIS_MODEL_CACHED_LOCALLY"] = "true"
        os.environ["HF_HUB_OFFLINE"] = "1"  # Tell HuggingFace to use offline mode
        logger.info("Set HF_HUB_OFFLINE=1 to force HuggingFace to use local cache")

        # Verify downloaded files exist
        logger.info("Verifying downloaded files...")
        downloaded_safetensors = list(hf_cache_path.rglob("*.safetensors"))
        downloaded_bin = list(hf_cache_path.rglob("*.bin"))
        logger.info(f"Verified: {len(downloaded_safetensors)} .safetensors files")
        logger.info(f"Verified: {len(downloaded_bin)} .bin files")

        if downloaded_safetensors or downloaded_bin:
            logger.info("Sample downloaded files:")
            for f in (downloaded_safetensors + downloaded_bin)[:5]:
                logger.info(f"  ✓ {f}")

        logger.info("=" * 80)
        logger.info(
            f"✅ Model downloaded successfully! ({downloaded_count} files to {hf_cache_path})"
        )
        logger.info("=" * 80)
        return True

    except Exception as e:
        import traceback

        logger.error("=" * 80)
        logger.error("GCS MODEL DOWNLOAD FAILED")
        logger.error("=" * 80)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("Full traceback:")
        logger.error(traceback.format_exc())

        logger.error("=" * 80)
        logger.error("ATTEMPTED CONFIGURATION:")
        logger.error("=" * 80)
        logger.error(f"  Model name: {model_name}")
        logger.error(f"  Model name (cleaned): {model_name_clean}")
        logger.error(f"  GCS bucket: {model_bucket}")
        logger.error(f"  GCS path: gs://{model_bucket}/{model_path}/")
        logger.error(f"  Local cache directory: {local_cache_dir}")
        logger.error(f"  Local cache path: {local_cache_path}")
        logger.error(f"  HuggingFace model dir: {hf_model_dir}")
        logger.error(f"  HuggingFace cache path: {hf_cache_path}")
        logger.error(f"  Force download: {force_download}")

        logger.error("=" * 80)
        logger.error("ENVIRONMENT CHECK:")
        logger.error("=" * 80)
        logger.error(f"  TRANSFORMERS_CACHE: {os.environ.get('TRANSFORMERS_CACHE', 'NOT SET')}")
        logger.error(f"  MODEL_BUCKET: {os.environ.get('MODEL_BUCKET', 'NOT SET')}")
        logger.error(f"  DEFAULT_MODEL: {os.environ.get('DEFAULT_MODEL', 'NOT SET')}")
        logger.error(f"  HF_HUB_OFFLINE: {os.environ.get('HF_HUB_OFFLINE', 'NOT SET')}")

        logger.error("=" * 80)
        logger.error("TROUBLESHOOTING STEPS:")
        logger.error("=" * 80)
        logger.error("1. Verify model exists at: gs://{model_bucket}/{model_path}/")
        logger.error("2. Check service account has 'Storage Object Viewer' permissions")
        logger.error("3. Verify MODEL_BUCKET environment variable is correct")
        logger.error("4. Verify DEFAULT_MODEL environment variable matches GCS path structure")
        logger.error("5. Check GCS bucket name and path prefix match exactly")
        logger.error("=" * 80)

        # Try to provide more specific error information
        error_str = str(e).lower()
        if "permission" in error_str or "access" in error_str or "forbidden" in error_str:
            logger.error("ERROR TYPE: Permission/Access Issue")
            logger.error("  -> Check service account permissions on GCS bucket")
        elif "not found" in error_str or "does not exist" in error_str:
            logger.error("ERROR TYPE: Resource Not Found")
            logger.error("  -> Verify bucket name and path are correct")
        elif "network" in error_str or "connection" in error_str or "timeout" in error_str:
            logger.error("ERROR TYPE: Network/Connection Issue")
            logger.error("  -> Check network connectivity to GCS")
        else:
            logger.error("ERROR TYPE: Unknown - see traceback above")

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

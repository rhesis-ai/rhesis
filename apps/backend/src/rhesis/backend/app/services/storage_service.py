import os
from pathlib import Path
from typing import Optional

import fsspec

from rhesis.backend.logging import logger


class StorageService:
    """Handles low-level file storage operations with Google Cloud Storage and backend storage."""

    def __init__(self):
        """Initialize StorageService with configuration from environment variables."""
        self.bucket_name = self._get_bucket_name()
        self.project_id = os.getenv("STORAGE_PROJECT_ID")
        self.credentials_path = os.getenv("STORAGE_CREDENTIALS_PATH")
        self.storage_path = os.getenv("LOCAL_STORAGE_PATH", "/tmp/rhesis-files")

        # Check if GCS is configured (credentials_path optional for Cloud Run)
        self.use_gcs = all([self.bucket_name, self.project_id])

        # Initialize file system
        self.fs = self._get_file_system()

        if self.use_gcs:
            logger.info(f"StorageService initialized with cloud storage bucket: {self.bucket_name}")
        else:
            logger.warning(
                "StorageService using ephemeral container storage - files will be lost on restart"
            )

    def _get_bucket_name(self) -> Optional[str]:
        """Get environment-specific bucket name."""
        env_mapping = {
            "local": None,  # Use local storage
            "production": "prd",
            "staging": "stg",
            "development": "dev",
        }

        backend_env = os.getenv("BACKEND_ENV", "").lower()
        env_suffix = env_mapping.get(backend_env, "dev")  # Default to dev

        if env_suffix is None:
            logger.info("Local environment detected - using local file storage")
            return None

        bucket_name = f"sources-rhesis-{env_suffix}"
        logger.info(f"Using environment-specific storage bucket: {bucket_name}")
        return bucket_name

    def _get_file_system(self):
        """Get file system - cloud storage if configured, otherwise temporary storage."""
        if self.use_gcs:
            if self.credentials_path:
                # Local development: use explicit credentials file
                return fsspec.filesystem(
                    "gcs", project=self.project_id, token=self.credentials_path
                )
            else:
                # Production: use service account attached to Cloud Run
                return fsspec.filesystem("gcs", project=self.project_id)
        else:
            # Fallback to temporary storage
            return fsspec.filesystem("file")

    def get_file_path(self, organization_id: str, source_id: str, filename: str) -> str:
        """Generate file path for multi-tenant storage."""
        if self.use_gcs:
            # Cloud storage path: bucket/org_id/source_id_filename
            return f"{self.bucket_name}/{organization_id}/{source_id}_{filename}"
        else:
            # Temporary storage path: /tmp/rhesis-files/org_id/source_id_filename
            logger.info(
                f"Cloud storage not configured, saving file to temp storage: {self.storage_path}"
            )
            storage_dir = Path(self.storage_path) / organization_id
            storage_dir.mkdir(parents=True, exist_ok=True)
            return str(storage_dir / f"{source_id}_{filename}")

    async def save_file(self, content: bytes, file_path: str) -> str:
        """Save file content to storage."""
        with self.fs.open(file_path, "wb") as f:
            f.write(content)
        return file_path

    async def get_file(self, file_path: str) -> bytes:
        """Retrieve file content from storage."""
        with self.fs.open(file_path, "rb") as f:
            return f.read()

    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage."""
        try:
            self.fs.rm(file_path)
            return True
        except Exception:
            return False

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in storage."""
        try:
            return self.fs.exists(file_path)
        except Exception:
            return False

    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes."""
        try:
            return self.fs.size(file_path)
        except Exception:
            return None

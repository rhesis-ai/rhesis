import base64
import json
import os
from pathlib import Path
from typing import Optional

import fsspec
from google.oauth2 import service_account

from rhesis.backend.logging import logger


class StorageService:
    """Handles low-level file storage operations with Google Cloud Storage and backend storage."""

    def __init__(self):
        """Initialize StorageService with configuration from environment variables."""
        self.storage_uri = os.getenv("STORAGE_SERVICE_URI")
        self.service_account_key = os.getenv("STORAGE_SERVICE_ACCOUNT_KEY")
        self.storage_path = os.getenv("LOCAL_STORAGE_PATH", "/tmp/rhesis-files")

        # Check if cloud storage is configured
        self.use_cloud_storage = all([self.storage_uri, self.service_account_key])

        # Initialize file system
        self.fs = self._get_file_system()

        if self.use_cloud_storage:
            logger.info(f"StorageService initialized with cloud storage URI: {self.storage_uri}")
        else:
            logger.warning(
                "StorageService using ephemeral container storage - files will be lost on restart"
            )

    def _get_file_system(self):
        """Get file system - cloud storage if configured, otherwise temporary storage."""
        if self.use_cloud_storage:
            try:
                # Parse base64-encoded service account key from environment variable
                # Clean the base64 string (remove whitespace/newlines)
                clean_base64 = (
                    self.service_account_key.strip()
                    .replace("\n", "")
                    .replace("\r", "")
                    .replace(" ", "")
                )
                decoded_key = base64.b64decode(clean_base64).decode("utf-8")

                # Fix the private key formatting - escape actual newlines in JSON
                decoded_key = decoded_key.replace("\n", "\\n")

                service_account_info = json.loads(decoded_key)

                # Create credentials object with explicit scopes for GCS
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )

                fs = fsspec.filesystem("gcs", project=credentials.project_id, token=credentials)
                return fs
            except Exception as e:
                logger.error(f"Failed to initialize GCS filesystem: {str(e)}", exc_info=True)
                logger.warning("Falling back to local filesystem due to GCS error")
                return fsspec.filesystem("file")
        else:
            logger.info("Using local filesystem (cloud storage not configured)")
            # Fallback to temporary storage
            return fsspec.filesystem("file")

    def get_file_path(self, organization_id: str, source_id: str, filename: str) -> str:
        """Generate file path for multi-tenant storage."""
        if self.use_cloud_storage:
            # Extract bucket name from storage URI
            # (e.g., "gs://sources-rhesis-dev" -> "sources-rhesis-dev")
            bucket_name = self.storage_uri.replace("gs://", "")
            # Cloud storage path: bucket_name/org_id/source_id_filename
            return f"{bucket_name}/{organization_id}/{source_id}_{filename}"
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

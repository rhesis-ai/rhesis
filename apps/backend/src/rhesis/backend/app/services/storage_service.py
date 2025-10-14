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

    def _get_local_path(self, file_path: str) -> str:
        """Convert cloud storage path to local storage path.

        Args:
            file_path: Cloud storage path (e.g., "bucket_name/org_id/source_id_filename")

        Returns:
            str: Local file path
        """
        if self.use_cloud_storage and "/" in file_path:
            # Extract the path after bucket name (e.g., "org_id/source_id_filename")
            path_parts = file_path.split("/", 1)
            if len(path_parts) > 1:
                relative_path = path_parts[1]
                return str(Path(self.storage_path) / relative_path)

        # If it's already a local path or malformed cloud path, return as-is
        return file_path

    async def save_file(self, content: bytes, file_path: str) -> str:
        """Save file content to storage."""
        with self.fs.open(file_path, "wb") as f:
            f.write(content)
        return file_path

    async def get_file(self, file_path: str) -> bytes:
        """Retrieve file content from storage with hybrid lookup.

        First tries cloud storage (if configured), then falls back to local storage.
        This allows for gradual migration from local to cloud storage.
        """
        # Try cloud storage first (if configured)
        if self.use_cloud_storage:
            try:
                with self.fs.open(file_path, "rb") as f:
                    content = f.read()
                    logger.debug(f"Retrieved file from cloud storage: {file_path}")
                    return content
            except FileNotFoundError:
                logger.debug(f"File not found in cloud storage, checking local: {file_path}")
            except Exception as e:
                logger.warning(f"Error accessing cloud storage for {file_path}: {str(e)}")

        # Try local storage
        local_path = self._get_local_path(file_path)
        if os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    content = f.read()
                    logger.debug(f"Retrieved file from local storage: {local_path}")
                    return content
            except Exception as e:
                logger.error(f"Error reading local file {local_path}: {str(e)}")

        raise FileNotFoundError(f"File not found in cloud or local storage: {file_path}")

    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage."""
        try:
            self.fs.rm(file_path)
            return True
        except Exception:
            return False

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in storage with hybrid lookup.

        Checks both cloud storage (if configured) and local storage.
        """
        # Check cloud storage first (if configured)
        if self.use_cloud_storage:
            try:
                if self.fs.exists(file_path):
                    logger.debug(f"File exists in cloud storage: {file_path}")
                    return True
            except Exception as e:
                logger.warning(f"Error checking cloud storage for {file_path}: {str(e)}")

        # Check local storage
        local_path = self._get_local_path(file_path)
        if os.path.exists(local_path):
            logger.debug(f"File exists in local storage: {local_path}")
            return True

        logger.debug(f"File not found in cloud or local storage: {file_path}")
        return False

    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes with hybrid lookup."""
        # Try cloud storage first (if configured)
        if self.use_cloud_storage:
            try:
                size = self.fs.size(file_path)
                if size is not None:
                    logger.debug(f"File size from cloud storage: {file_path} ({size} bytes)")
                    return size
            except Exception as e:
                logger.warning(
                    f"Error getting file size from cloud storage for {file_path}: {str(e)}"
                )

        # Try local storage
        local_path = self._get_local_path(file_path)
        if os.path.exists(local_path):
            try:
                size = os.path.getsize(local_path)
                logger.debug(f"File size from local storage: {local_path} ({size} bytes)")
                return size
            except Exception as e:
                logger.error(f"Error getting local file size for {local_path}: {str(e)}")

        return None

    async def migrate_file_to_cloud(self, file_path: str) -> bool:
        """Migrate a file from local storage to cloud storage.

        This is useful for gradually moving files from local to cloud storage.

        Args:
            file_path: Cloud storage path where the file should be stored

        Returns:
            bool: True if migration was successful, False otherwise
        """
        if not self.use_cloud_storage:
            logger.warning("Cloud storage not configured, cannot migrate file")
            return False

        local_path = self._get_local_path(file_path)
        if not os.path.exists(local_path):
            logger.warning(f"Local file not found for migration: {local_path}")
            return False

        try:
            # Read local file
            with open(local_path, "rb") as f:
                content = f.read()

            # Save to cloud storage
            await self.save_file(content, file_path)

            # Verify cloud storage
            if self.fs.exists(file_path):
                logger.info(f"Successfully migrated file to cloud storage: {file_path}")
                return True
            else:
                logger.error(f"File migration failed - not found in cloud storage: {file_path}")
                return False

        except Exception as e:
            logger.error(f"Error migrating file {local_path} to cloud storage: {str(e)}")
            return False

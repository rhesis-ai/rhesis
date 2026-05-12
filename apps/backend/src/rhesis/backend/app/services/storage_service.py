import asyncio
import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

import fsspec
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192  # bytes per streaming chunk


class NotSupportedError(Exception):
    """Raised when an operation is not supported by the current storage backend."""


class StorageService:
    """Handles low-level file storage operations.

    Backend-agnostic by construction: configured via ``STORAGE_SERVICE_URI``
    which accepts ``gs://``, ``s3://``, ``file://``, or any fsspec-supported
    scheme. Existing ``gs://...`` values keep working unchanged.
    """

    def __init__(self):
        self.storage_uri = os.getenv("STORAGE_SERVICE_URI")
        self.service_account_key = os.getenv("STORAGE_SERVICE_ACCOUNT_KEY")
        self.storage_path = os.getenv("LOCAL_STORAGE_PATH", "/tmp/rhesis-files")

        self._protocol, self._bucket_or_root = self._parse_uri(self.storage_uri)
        self._credentials = None  # populated for gcs protocol

        # ``_get_file_system`` may downgrade ``_protocol`` to ``"file"`` if the
        # requested cloud backend can't be initialised (e.g. ``gs://`` with no
        # service-account key, or boto3 import failure). Compute the public
        # ``use_cloud_storage`` flag *after* initialisation so it reflects what
        # the service actually does, not just what was configured.
        self.fs = self._get_file_system()
        self.use_cloud_storage = self._protocol in ("gcs", "gs", "s3", "s3a")

        if self.use_cloud_storage:
            logger.info(
                f"StorageService initialised with cloud storage URI: {self.storage_uri}"
                f" (protocol={self._protocol})"
            )
        else:
            logger.warning(
                "StorageService using local/ephemeral storage — files will be lost on restart. "
                "Set STORAGE_SERVICE_URI to a cloud URI for persistent storage."
            )

    # ------------------------------------------------------------------
    # URI parsing
    # ------------------------------------------------------------------

    def _parse_uri(self, uri: Optional[str]) -> tuple:
        """Return (protocol, bucket_or_root) from a storage URI.

        Handles:
          - ``gs://bucket-name``        → (gcs, bucket-name)
          - ``gcs://bucket-name``       → (gcs, bucket-name)
          - ``s3://bucket-name``        → (s3, bucket-name)
          - ``file:///abs/path``        → (file, /abs/path)
          - None / missing              → (file, self.storage_path)
        """
        if not uri:
            return ("file", self.storage_path)

        parsed = urlparse(uri)
        scheme = parsed.scheme.lower()

        if scheme in ("gs", "gcs"):
            return ("gcs", parsed.netloc)
        if scheme in ("s3", "s3a"):
            return ("s3", parsed.netloc)
        if scheme == "file":
            root = parsed.path or self.storage_path
            return ("file", root)

        # Unknown scheme: fall back to local
        logger.warning(
            f"Unknown STORAGE_SERVICE_URI scheme '{scheme}' — falling back to local filesystem"
        )
        return ("file", self.storage_path)

    # ------------------------------------------------------------------
    # Filesystem initialisation
    # ------------------------------------------------------------------

    def _get_file_system(self):
        """Instantiate the fsspec filesystem for the active protocol.

        Downgrades ``self._protocol`` to ``"file"`` on any cloud-init failure
        (missing credentials, unimportable client library, etc.) so callers
        relying on ``use_cloud_storage`` see the *effective* backend, not the
        configured-but-unusable one.
        """
        if self._protocol == "gcs":
            if not self.service_account_key:
                logger.warning(
                    "STORAGE_SERVICE_URI points to GCS but STORAGE_SERVICE_ACCOUNT_KEY is not set."
                    " Falling back to local filesystem."
                )
                self._protocol = "file"
                self._bucket_or_root = self.storage_path
                return fsspec.filesystem("file")
            try:
                clean_b64 = (
                    self.service_account_key.strip()
                    .replace("\n", "")
                    .replace("\r", "")
                    .replace(" ", "")
                )
                decoded = base64.b64decode(clean_b64).decode("utf-8")
                sa_info = json.loads(decoded)
                self._credentials = service_account.Credentials.from_service_account_info(
                    sa_info,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                fs = fsspec.filesystem(
                    "gcs",
                    project=self._credentials.project_id,
                    token=self._credentials,
                )
                return fs
            except Exception as e:
                logger.error(f"Failed to initialise GCS filesystem: {e}", exc_info=True)
                logger.warning("Falling back to local filesystem due to GCS error")
                self._protocol = "file"
                self._bucket_or_root = self.storage_path
                return fsspec.filesystem("file")

        if self._protocol in ("s3", "s3a"):
            # boto3/s3fs credentials resolved from env (AWS_ACCESS_KEY_ID etc.)
            try:
                return fsspec.filesystem("s3")
            except Exception as e:
                logger.error(f"Failed to initialise S3 filesystem: {e}", exc_info=True)
                self._protocol = "file"
                self._bucket_or_root = self.storage_path
                return fsspec.filesystem("file")

        # file:// or fallback
        return fsspec.filesystem("file")

    # ------------------------------------------------------------------
    # Internal path resolution
    # ------------------------------------------------------------------

    def _full_path(self, relative_path: str) -> str:
        """Prepend bucket/root to a relative storage path if needed."""
        if self._protocol == "gcs":
            return f"{self._bucket_or_root}/{relative_path}"
        if self._protocol in ("s3", "s3a"):
            return f"{self._bucket_or_root}/{relative_path}"
        # file://
        root = self._bucket_or_root or self.storage_path
        return str(Path(root) / relative_path)

    # ------------------------------------------------------------------
    # Legacy compatibility: path builder for sources
    # ------------------------------------------------------------------

    def get_file_path(self, organization_id: str, source_id: str, filename: str) -> str:
        """Generate file path for multi-tenant source storage (legacy).

        For the local filesystem backend the per-org directory is created here
        so the legacy ``save_file`` API (which uses fsspec's plain ``open``)
        can write the file directly. Cloud backends create directories
        implicitly on PUT, so we skip the mkdir there.
        """
        relative = f"{organization_id}/{source_id}_{filename}"
        full_path = self._full_path(relative)
        if self._protocol == "file":
            storage_dir = Path(self._bucket_or_root or self.storage_path) / organization_id
            storage_dir.mkdir(parents=True, exist_ok=True)
            return str(storage_dir / f"{source_id}_{filename}")
        return full_path

    def _get_local_path(self, file_path: str) -> str:
        """Convert cloud storage path to local storage path (legacy helper)."""
        if self.use_cloud_storage and "/" in file_path:
            path_parts = file_path.split("/", 1)
            if len(path_parts) > 1:
                relative_path = path_parts[1]
                return str(Path(self.storage_path) / relative_path)
        return file_path

    # ------------------------------------------------------------------
    # Domain-scoped path builders
    # ------------------------------------------------------------------

    def get_source_path(self, organization_id: str, source_id: str, filename: str) -> str:
        """Legacy: {org_id}/{source_id}_{filename}. Alias of get_file_path."""
        return self.get_file_path(organization_id, source_id, filename)

    def get_attachment_prefix(
        self,
        organization_id: str,
        entity_type: str,
        entity_id: str,
        file_id: str,
    ) -> str:
        """Return the attachments/ prefix for a specific file entity."""
        return f"attachments/{organization_id}/{entity_type}/{entity_id}/{file_id}"

    def get_attachment_original_path(
        self,
        organization_id: str,
        entity_type: str,
        entity_id: str,
        file_id: str,
        filename: str,
    ) -> str:
        """{prefix}/original{ext}  — ext derived from filename, '.bin' if none."""
        suffix = Path(filename).suffix or ".bin"
        prefix = self.get_attachment_prefix(organization_id, entity_type, entity_id, file_id)
        return f"{prefix}/original{suffix}"

    def get_attachment_thumbnail_path(
        self,
        organization_id: str,
        entity_type: str,
        entity_id: str,
        file_id: str,
        size: int,
    ) -> str:
        """{prefix}/thumb-{size}.webp"""
        prefix = self.get_attachment_prefix(organization_id, entity_type, entity_id, file_id)
        return f"{prefix}/thumb-{size}.webp"

    # ------------------------------------------------------------------
    # Streaming primitives
    # ------------------------------------------------------------------

    async def put_object_streaming(
        self,
        source: AsyncIterator[bytes],
        dest_path: str,
        content_type: str,
    ) -> tuple:
        """Stream bytes to storage and return (storage_path, sha256_hex).

        Chunks are forwarded directly to the fsspec write stream so the full
        body never resides in Python memory as a single buffer.
        """
        full_path = self._full_path(dest_path)

        # Ensure parent directory exists (relevant for file:// backend)
        if self._protocol == "file":
            Path(full_path).parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256()

        try:
            with self.fs.open(full_path, "wb") as f:
                async for chunk in source:
                    if chunk:
                        f.write(chunk)
                        sha256.update(chunk)
        except Exception as e:
            # Attempt cleanup on error
            try:
                self.fs.rm(full_path)
            except Exception:
                pass
            raise e

        return dest_path, sha256.hexdigest()

    def put_object_bytes(
        self,
        content: bytes,
        dest_path: str,
        content_type: str,  # noqa: ARG002 — kept for parity with put_object_streaming
    ) -> tuple:
        """Synchronously write ``content`` to storage and return ``(storage_path, sha256_hex)``.

        Synchronous sibling of :meth:`put_object_streaming`.  Use this when the
        bytes are already fully materialised in memory (e.g.  base64-decoded
        sanitiser output that we want to externalise from a JSONB column) and
        the caller is on a sync code path that already has an event loop
        running on its thread — creating a second loop with
        ``asyncio.new_event_loop().run_until_complete(...)`` would raise
        ``RuntimeError: Cannot run the event loop while another loop is
        running``.

        ``content_type`` is accepted for signature parity but is not stored
        here; the caller persists it in the ``File`` metadata row.
        """
        full_path = self._full_path(dest_path)

        if self._protocol == "file":
            Path(full_path).parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256()
        sha256.update(content)

        try:
            with self.fs.open(full_path, "wb") as f:
                f.write(content)
        except Exception:
            try:
                self.fs.rm(full_path)
            except Exception:
                pass
            raise

        return dest_path, sha256.hexdigest()

    async def get_object_stream(self, path: str) -> AsyncIterator[bytes]:
        """Yield chunks from storage asynchronously."""
        full_path = self._full_path(path)

        async def _generate():
            loop = asyncio.get_event_loop()
            with self.fs.open(full_path, "rb") as f:
                while True:
                    chunk = await loop.run_in_executor(None, f.read, CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk

        return _generate()

    async def generate_presigned_url(
        self,
        path: str,
        expires_in: int = 300,
        response_disposition: Optional[str] = None,
    ) -> str:
        """Return a presigned URL for direct client download.

        Dispatches by backend protocol:
          - gcs  → google.cloud.storage V4 signed URL (service-account JSON key)
          - s3   → boto3 presigned_url (stub — raises NotSupportedError)
          - file → raises NotSupportedError (caller falls back to StreamingResponse)
        """
        if self._protocol == "gcs":
            return await self._gcs_presigned_url(path, expires_in, response_disposition)
        if self._protocol in ("s3", "s3a"):
            raise NotSupportedError("S3 presigned URLs not yet implemented")
        raise NotSupportedError("Local filesystem does not support presigned URLs")

    async def _gcs_presigned_url(
        self,
        path: str,
        expires_in: int,
        response_disposition: Optional[str],
    ) -> str:
        """Generate a GCS V4 signed URL using the service-account JSON key."""
        import datetime

        from google.cloud import storage as gcs_storage

        clean_b64 = (
            self.service_account_key.strip().replace("\n", "").replace("\r", "").replace(" ", "")
        )
        decoded = base64.b64decode(clean_b64).decode("utf-8")
        sa_info = json.loads(decoded)

        client = gcs_storage.Client.from_service_account_info(sa_info)
        bucket = client.bucket(self._bucket_or_root)
        blob = bucket.blob(path)

        kwargs = {
            "version": "v4",
            "expiration": datetime.timedelta(seconds=expires_in),
            "method": "GET",
        }
        if response_disposition:
            kwargs["response_disposition"] = response_disposition

        # Cloud Storage signing is synchronous; offload to threadpool
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(None, lambda: blob.generate_signed_url(**kwargs))
        return url

    async def delete_object(self, path: str) -> bool:
        """Delete an object from storage. Returns True on success."""
        return await self.delete_file(self._full_path(path))

    # ------------------------------------------------------------------
    # Legacy API (unchanged — Source/DocumentHandler callers)
    # ------------------------------------------------------------------

    async def save_file(self, content: bytes, file_path: str) -> str:
        """Save file content to storage (legacy full-buffer API)."""
        with self.fs.open(file_path, "wb") as f:
            f.write(content)
        return file_path

    async def get_file(self, file_path: str) -> bytes:
        """Retrieve file content from storage with hybrid lookup."""
        if self.use_cloud_storage:
            try:
                with self.fs.open(file_path, "rb") as f:
                    return f.read()
            except FileNotFoundError:
                logger.debug(f"File not found in cloud storage, checking local: {file_path}")
            except Exception as e:
                logger.warning(f"Error accessing cloud storage for {file_path}: {e}")

        local_path = self._get_local_path(file_path)
        if os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading local file {local_path}: {e}")

        raise FileNotFoundError(f"File not found in cloud or local storage: {file_path}")

    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage."""
        try:
            self.fs.rm(file_path)
            return True
        except Exception:
            return False

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in storage with hybrid lookup."""
        if self.use_cloud_storage:
            try:
                if self.fs.exists(file_path):
                    return True
            except Exception as e:
                logger.warning(f"Error checking cloud storage for {file_path}: {e}")

        local_path = self._get_local_path(file_path)
        if os.path.exists(local_path):
            return True

        return False

    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes with hybrid lookup."""
        if self.use_cloud_storage:
            try:
                size = self.fs.size(file_path)
                if size is not None:
                    return size
            except Exception as e:
                logger.warning(f"Error getting file size from cloud storage for {file_path}: {e}")

        local_path = self._get_local_path(file_path)
        if os.path.exists(local_path):
            try:
                return os.path.getsize(local_path)
            except Exception as e:
                logger.error(f"Error getting local file size for {local_path}: {e}")

        return None

    async def migrate_file_to_cloud(self, file_path: str) -> bool:
        """Migrate a file from local storage to cloud storage (legacy helper)."""
        if not self.use_cloud_storage:
            logger.warning("Cloud storage not configured, cannot migrate file")
            return False

        local_path = self._get_local_path(file_path)
        if not os.path.exists(local_path):
            logger.warning(f"Local file not found for migration: {local_path}")
            return False

        try:
            with open(local_path, "rb") as f:
                content = f.read()
            await self.save_file(content, file_path)
            if self.fs.exists(file_path):
                return True
            return False
        except Exception as e:
            logger.error(f"Error migrating file {local_path} to cloud storage: {e}")
            return False

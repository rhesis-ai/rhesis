from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from rhesis.backend.app.services.storage_service import StorageService

from .base import BaseSourceHandler


class DocumentHandler(BaseSourceHandler):
    """Handles persistent document storage with cloud/local backend."""

    def __init__(
        self,
        storage_service: Optional[StorageService] = None,
        max_size: int = 5 * 1024 * 1024,  # 5MB default
    ):
        """
        Initialize DocumentHandler with storage service and max size.

        Args:
            storage_service: StorageService instance for file operations
            max_size: Maximum allowed document size in bytes (default 5MB)
        """
        self.storage_service = storage_service or StorageService()
        self.max_size = max_size

    async def save_source(
        self,
        file: UploadFile,
        organization_id: str,
        source_id: str,
        user_id: str = None,
        db_session=None,
    ) -> dict:
        """
        Save uploaded source to persistent storage.

        Args:
            file: FastAPI UploadFile object
            organization_id: Organization ID for multi-tenant storage
            source_id: Source ID for unique file naming
            user_id: User ID who uploaded the file (optional)
            db_session: Database session for user lookup (optional)

        Returns:
            dict: File metadata (size, hash, path, etc.)

        Raises:
            ValueError: If source size exceeds limit or is empty
        """
        if not file.filename or not file.filename.strip():
            raise ValueError("Source has no name")

        # Read source content to check size
        content = await file.read()
        if len(content) > self.max_size:
            raise ValueError(f"Source size exceeds limit of {self.max_size} bytes")
        if len(content) == 0:
            raise ValueError("Source is empty")

        # Generate file path
        file_path = self.storage_service.get_file_path(organization_id, source_id, file.filename)

        # Save to storage
        await self.storage_service.save_file(content, file_path)

        # Get metadata including file_path and uploader name
        metadata = self._extract_metadata(
            content, file.filename, file_path, user_id, organization_id, db_session
        )

        return metadata

    async def get_source_content(self, file_path: str) -> bytes:
        """
        Retrieve source content from storage.

        Args:
            file_path: Path to the source in storage

        Returns:
            bytes: Source content
        """
        return await self.storage_service.get_file(file_path)

    async def delete_source(self, file_path: str) -> bool:
        """
        Delete source from storage.

        Args:
            file_path: Path to the source in storage

        Returns:
            bool: True if successful, False otherwise
        """
        return await self.storage_service.delete_file(file_path)

    async def extract_source_content(self, file_path: str) -> str:
        """
        Extract text content from a source stored in cloud storage.

        Args:
            file_path: Path to the source in storage

        Returns:
            str: Extracted text content

        Raises:
            ValueError: If extraction fails or file format is not supported
        """
        from rhesis.sdk.services.extractor import DocumentExtractor

        # Get file content from storage
        file_content = await self.get_source_content(file_path)

        extractor = DocumentExtractor()
        return extractor.extract_from_bytes(file_content, Path(file_path).name)

    def _extract_metadata(
        self,
        content: bytes,
        filename: str,
        file_path: str,
        user_id: str = None,
        organization_id: str = None,
        db_session=None,
    ) -> dict:
        """Extract file metadata (file-specific information only)."""
        metadata = {
            "file_size": len(content),
            "file_hash": self._calculate_file_hash(content),
            "original_filename": filename,
            "file_type": self._get_mime_type(filename),
            "file_path": file_path,
        }

        return metadata

    def _calculate_file_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of file content."""
        import hashlib

        return hashlib.sha256(content).hexdigest()

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename."""
        ext = Path(filename).suffix.lower()
        mime_types = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".html": "text/html",
            ".csv": "text/csv",
            ".json": "application/json",
            ".xml": "application/xml",
            ".zip": "application/zip",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return mime_types.get(ext, "application/octet-stream")

    # Backward compatibility methods for services router
    async def save_document(
        self,
        document: UploadFile,
        organization_id: str,
        source_id: str,
    ) -> dict:
        """Backward compatibility method - delegates to save_source."""
        return await self.save_source(document, organization_id, source_id)

    async def get_document_content(self, file_path: str) -> bytes:
        """Backward compatibility method - delegates to get_source_content."""
        return await self.get_source_content(file_path)

    async def delete_document(self, file_path: str) -> bool:
        """Backward compatibility method - delegates to delete_source."""
        return await self.delete_source(file_path)

    async def extract_document_content(self, file_path: str) -> str:
        """Backward compatibility method - delegates to extract_source_content."""
        return await self.extract_source_content(file_path)

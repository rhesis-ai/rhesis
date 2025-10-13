from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from rhesis.backend.app.services.storage_service import StorageService


class SourceHandler:
    """Handles source storage with cloud/local backend for persistent storage."""

    def __init__(
        self,
        storage_service: Optional[StorageService] = None,
        max_size: int = 5 * 1024 * 1024,  # 5MB default
    ):
        """
        Initialize SourceHandler with storage service and max size.

        Args:
            storage_service: StorageService instance for file operations
            max_size: Maximum allowed document size in bytes (default 5MB)
        """
        self.storage_service = storage_service or StorageService()
        self.max_size = max_size

    async def save_document(
        self,
        document: UploadFile,
        organization_id: str,
        source_id: str,
    ) -> dict:
        """
        Save uploaded document to persistent storage.

        Args:
            document: FastAPI UploadFile object
            organization_id: Organization ID for multi-tenant storage
            source_id: Source ID for unique file naming

        Returns:
            dict: File metadata (size, hash, path, etc.)

        Raises:
            ValueError: If document size exceeds limit or is empty
        """
        if not document.filename or not document.filename.strip():
            raise ValueError("Document has no name")

        # Read document content to check size
        content = await document.read()
        if len(content) > self.max_size:
            raise ValueError(f"Document size exceeds limit of {self.max_size} bytes")
        if len(content) == 0:
            raise ValueError("Document is empty")

        # Generate file path
        file_path = self.storage_service.get_file_path(
            organization_id, source_id, document.filename
        )

        # Save to storage
        await self.storage_service.save_file(content, file_path)

        # Get metadata including file_path
        metadata = self._extract_metadata(content, document.filename, file_path)

        return metadata

    async def get_document_content(self, file_path: str) -> bytes:
        """
        Retrieve document content from storage.

        Args:
            file_path: Path to the document in storage

        Returns:
            bytes: Document content
        """
        return await self.storage_service.get_file(file_path)

    async def delete_document(self, file_path: str) -> bool:
        """
        Delete document from storage.

        Args:
            file_path: Path to the document in storage

        Returns:
            bool: True if successful, False otherwise
        """
        return await self.storage_service.delete_file(file_path)

    async def extract_document_content(self, file_path: str) -> str:
        """
        Extract text content from a document stored in cloud storage.

        Args:
            file_path: Path to the document in storage

        Returns:
            str: Extracted text content

        Raises:
            ValueError: If extraction fails or file format is not supported
        """
        from rhesis.sdk.services.extractor import DocumentExtractor

        # Get file content from storage
        file_content = await self.get_document_content(file_path)

        extractor = DocumentExtractor()
        return extractor.extract_from_bytes(file_content, Path(file_path).name)

    def _extract_metadata(self, content: bytes, filename: str, file_path: str) -> dict:
        """Extract file metadata including file path."""
        return {
            "file_size": len(content),
            "file_hash": self._calculate_file_hash(content),
            "uploaded_at": str(datetime.now(timezone.utc)),
            "original_filename": filename,
            "file_type": self._get_mime_type(filename),
            "file_path": file_path,
        }

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

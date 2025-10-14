from abc import ABC, abstractmethod

from fastapi import UploadFile


class BaseSourceHandler(ABC):
    """Abstract base class for source handlers.

    Defines the interface that all source type handlers must implement.
    Each source type (Document, Website, API, etc.) will have its own
    concrete implementation of this base class.
    """

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_source_content(self, file_path: str) -> bytes:
        """
        Retrieve source content from storage.

        Args:
            file_path: Path to the source in storage

        Returns:
            bytes: Source content
        """
        pass

    @abstractmethod
    async def delete_source(self, file_path: str) -> bool:
        """
        Delete source from storage.

        Args:
            file_path: Path to the source in storage

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    @abstractmethod
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
        pass

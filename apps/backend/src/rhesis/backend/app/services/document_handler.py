import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import UploadFile

class DocumentHandler:
    """Handles temporary document storage with explicit cleanup."""
    
    def __init__(self, temp_dir: Optional[str] = None, max_size: int = 5 * 1024 * 1024):  # 5MB default
        """
        Initialize DocumentHandler with configurable temp directory and max size.
        
        Args:
            temp_dir: Optional custom temp directory path. If None, uses system temp dir
            max_size: Maximum allowed document size in bytes (default 5MB)
        """
        self.temp_dir = temp_dir or os.path.join(os.path.dirname(__file__), "temp")
        self.max_size = max_size
        self._saved_documents = set()
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)

    async def save_document(self, document: UploadFile) -> str:
        """
        Save uploaded document to temporary location with UUID prefix.
        
        Args:
            document: FastAPI UploadFile object
            
        Returns:
            str: Temporary path (e.g. 'uuid_filename.ext')
            
        Raises:
            ValueError: If document size exceeds limit or is empty
        """
        if not document.filename:
            raise ValueError("Document has no name")
            
        # Read document content to check size
        content = await document.read()
        if len(content) > self.max_size:
            raise ValueError(f"Document size exceeds limit of {self.max_size} bytes")
        if len(content) == 0:
            raise ValueError("Document is empty")
            
        # Reset document position after reading
        await document.seek(0)
        
        # Generate unique identifier
        ext = Path(document.filename).suffix
        document_id = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(self.temp_dir, document_id)
        
        # Save document
        with open(path, "wb") as f:
            f.write(content)
            
        self._saved_documents.add(document_id)
        return document_id

    def get_path(self, document_id: str) -> str:
        """
        Get full path for a temporary document.
        
        Args:
            document_id: The temporary identifier returned by save_document
            
        Returns:
            str: Full path to the temporary document
            
        Raises:
            FileNotFoundError: If document doesn't exist or wasn't created by this handler
        """
        if document_id not in self._saved_documents:
            raise FileNotFoundError(f"Document {document_id} not found or not created by this handler")
            
        path = os.path.join(self.temp_dir, document_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Document {document_id} no longer exists")
            
        return path

    async def cleanup(self, document_id: Optional[str] = None) -> None:
        """
        Remove specified document or all documents created by this handler instance.
        
        Args:
            document_id: Optional specific document to cleanup. If None, cleans up all documents.
        """
        if document_id is not None:
            if document_id in self._saved_documents:
                try:
                    path = os.path.join(self.temp_dir, document_id)
                    os.remove(path)
                    self._saved_documents.remove(document_id)
                except OSError:
                    pass  # Ignore errors during cleanup
        else:
            for doc_id in self._saved_documents.copy():
                try:
                    path = os.path.join(self.temp_dir, doc_id)
                    os.remove(path)
                except OSError:
                    pass  # Ignore errors during cleanup
            self._saved_documents.clear()

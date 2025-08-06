import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import UploadFile

class DocumentHandler:
    """Handles temporary document storage without registry - relies on UUID uniqueness."""
    
    def __init__(self, temp_dir: Optional[str] = None, max_size: int = 5 * 1024 * 1024):  # 5MB default
        """
        Initialize DocumentHandler with configurable temp directory and max size.
        
        Args:
            temp_dir: Optional custom temp directory path. If None, uses system temp dir
            max_size: Maximum allowed document size in bytes (default 5MB)
        """
        self.temp_dir = temp_dir or os.path.join(os.path.dirname(__file__), "temp")
        self.max_size = max_size
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)

    async def save_document(self, document: UploadFile) -> str:
        """
        Save uploaded document to temporary location with UUID prefix.
        
        Args:
            document: FastAPI UploadFile object
            
        Returns:
            str: Full path to the saved document (e.g. '/tmp/temp/uuid_filename.ext')
            
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
        
        # Generate unique filename
        ext = Path(document.filename).suffix
        filename = f"{uuid.uuid4().hex}{ext}"
        full_path = os.path.join(self.temp_dir, filename)
        
        # Save document
        with open(full_path, "wb") as f:
            f.write(content)
            
        return full_path

    async def cleanup(self, path: str) -> None:
        """
        Remove document at the specified path.
        
        Args:
            path: Full path to the document to cleanup.
        """
        try:
            os.remove(path)
        except OSError:
            pass  # File already gone or permission error

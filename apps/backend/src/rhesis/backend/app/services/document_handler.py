import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import UploadFile

class DocumentHandler:
    """Handles temporary document storage with automatic cleanup using async context manager."""
    
    def __init__(self, temp_dir: Optional[str] = None, max_file_size: int = 5 * 1024 * 1024):  # 5MB default
        """
        Initialize DocumentHandler with configurable temp directory and max file size.
        
        Args:
            temp_dir: Optional custom temp directory path. If None, uses system temp dir
            max_file_size: Maximum allowed file size in bytes (default 5MB)
        """
        self.temp_dir = temp_dir or os.path.join(os.path.dirname(__file__), "temp")
        self.max_file_size = max_file_size
        self._saved_files = set()
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup saved files on context exit."""
        await self.cleanup()

    async def save_file(self, file: UploadFile) -> str:
        """
        Save uploaded file to temporary location with UUID prefix.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            str: Temporary path (e.g. 'uuid_filename.ext')
            
        Raises:
            ValueError: If file size exceeds limit or file is empty
        """
        if not file.filename:
            raise ValueError("File has no name")
            
        # Read file content to check size
        content = await file.read()
        if len(content) > self.max_file_size:
            raise ValueError(f"File size exceeds limit of {self.max_file_size} bytes")
        if len(content) == 0:
            raise ValueError("File is empty")
            
        # Reset file position after reading
        await file.seek(0)
        
        # Generate unique filename
        ext = Path(file.filename).suffix
        temp_filename = f"{uuid.uuid4().hex}{ext}"
        temp_path = os.path.join(self.temp_dir, temp_filename)
        
        # Save file
        with open(temp_path, "wb") as f:
            f.write(content)
            
        self._saved_files.add(temp_filename)
        return temp_filename

    def get_path(self, filename: str) -> str:
        """
        Get full path for a temporary file.
        
        Args:
            filename: The temporary filename returned by save_file
            
        Returns:
            str: Full path to the temporary file
            
        Raises:
            FileNotFoundError: If file doesn't exist or wasn't created by this handler
        """
        if filename not in self._saved_files:
            raise FileNotFoundError(f"File {filename} not found or not created by this handler")
            
        full_path = os.path.join(self.temp_dir, filename)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File {filename} no longer exists")
            
        return full_path

    async def cleanup(self) -> None:
        """Remove all files created by this handler instance."""
        for filename in self._saved_files:
            try:
                os.remove(os.path.join(self.temp_dir, filename))
            except OSError:
                pass  # Ignore errors during cleanup
        self._saved_files.clear()

"""Document handler service for processing uploaded files and document specifications."""

from fastapi import UploadFile, HTTPException
import tempfile
import os
from typing import List, Dict, Optional
from pathlib import Path


class DocumentHandler:
    """Service for handling document uploads and processing for PromptSynthesizer."""

    def __init__(self):
        """Initialize the document handler."""
        self._temp_files: List[str] = []

    async def process_documents(
        self, 
        documents: Optional[List[Dict]], 
        files: Optional[List[UploadFile]] = None
    ) -> List[Dict]:
        """
        Process document specifications and files into the format expected by PromptSynthesizer.
        
        Args:
            documents: List of document specifications (name, description, content)
            files: Optional list of uploaded files
            
        Returns:
            List of processed document specifications
            
        Raises:
            HTTPException: If document processing fails or required fields are missing
        """
        processed_docs = []
        
        # Process JSON documents
        if documents:
            for doc in documents:
                if not doc.get('name') or not doc.get('content') or not doc.get('description'):
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Document must have 'name', 'content', and 'description' fields"
                    )
                processed_docs.append(doc)

        # Process uploaded files
        if files:
            for file in files:
                if not file.filename:
                    continue
                    
                try:
                    # Get file info for description
                    filename = file.filename
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    # Create temporary file
                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=file_ext
                    )
                    self._temp_files.append(temp_file.name)
                    
                    # Write uploaded content to temp file
                    content = await file.read()
                    temp_file.write(content)
                    temp_file.close()
                    
                    # Add to documents list
                    processed_docs.append({
                        "name": filename,
                        "description": f"Uploaded file: {filename}",
                        "path": temp_file.name
                    })
                    
                except Exception as e:
                    self.cleanup()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to process uploaded file '{filename}': {str(e)}"
                    )
        
        return processed_docs


    def cleanup(self):
        """Clean up any temporary files created during document processing."""
        for temp_file in self._temp_files:
            try:
                os.unlink(temp_file)
            except OSError:
                pass  # File already deleted or doesn't exist
        self._temp_files.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        self.cleanup()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with automatic cleanup."""
        self.cleanup() 
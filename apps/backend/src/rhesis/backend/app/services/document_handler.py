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
            documents: List of document specifications (name, description, path/content)
            files: Optional list of uploaded files
            
        Returns:
            List of processed document specifications
            
        Raises:
            HTTPException: If document path not found or processing fails
        """
        processed_docs = []
        
        # Process document specifications from request
        if documents:
            for doc in documents:
                # Validate document has required fields
                if not doc.get('name'):
                    raise HTTPException(
                        status_code=400, 
                        detail="Document must have a 'name' field"
                    )
                
                # If document has content, use it directly
                if doc.get('content'):
                    processed_docs.append(doc)
                    continue
                    
                # If document has a path, validate it exists
                if doc.get('path'):
                    path = Path(doc['path'])
                    if not path.exists():
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Document path not found: {doc['path']}"
                        )
                    processed_docs.append(doc)
                    continue
                
                # Neither content nor path provided
                raise HTTPException(
                    status_code=400,
                    detail=f"Document '{doc['name']}' must have either 'content' or 'path' field"
                )

        # Process uploaded files
        if files:
            for file in files:
                if not file.filename:
                    continue
                    
                try:
                    # Create temporary file with appropriate extension
                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=os.path.splitext(file.filename)[1]
                    )
                    self._temp_files.append(temp_file.name)
                    
                    # Write uploaded content to temporary file
                    content = await file.read()
                    temp_file.write(content)
                    temp_file.close()
                    
                    # Add to documents list with temp file path
                    processed_docs.append({
                        "name": file.filename,
                        "description": f"Uploaded file: {file.filename}",
                        "path": temp_file.name,
                        "content": None
                    })
                    
                except Exception as e:
                    # Clean up any temp files created before the error
                    self.cleanup()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to process uploaded file '{file.filename}': {str(e)}"
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
"""
Dependency injection functions for FastAPI.
"""
from functools import lru_cache
from typing import Optional, List, Dict, Tuple
import json

from fastapi import Depends, Form, File, UploadFile, HTTPException

from rhesis.backend.app.services.endpoint import EndpointService
from rhesis.backend.app.services.document_handler import DocumentHandler
from rhesis.backend.app.schemas.services import DocumentSpecification


@lru_cache()
def get_endpoint_service() -> EndpointService:
    """
    Get or create an EndpointService instance.
    Uses lru_cache to maintain a single instance per process while still allowing
    for proper dependency injection and testing.
    
    Returns:
        EndpointService: The endpoint service instance
    """
    return EndpointService() 

async def process_form_documents(
    files: Optional[List[UploadFile]] = File(None),
) -> Tuple[List[Dict], DocumentHandler]:
    """
    FastAPI dependency that processes uploaded files.
    
    Args:
        files: List of uploaded files
        
    Returns:
        Tuple of (processed_documents, document_handler)
        
    Raises:
        HTTPException: If file processing fails
    """
    handler = DocumentHandler()
    
    try:
        # Process files only
        processed_documents = await handler.process_documents(
            documents=None,  # No JSON documents for file upload endpoint
            files=files
        )
        
        return processed_documents, handler
        
    except Exception as e:
        handler.cleanup()
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(e))


async def process_json_documents(
    documents: Optional[List[DocumentSpecification]] = None
) -> Tuple[List[Dict], DocumentHandler]:
    """
    Process documents from DocumentSpecification objects (for JSON endpoints).
    
    Args:
        documents: List of DocumentSpecification objects with content and description
        
    Returns:
        Tuple of (processed_documents, document_handler)
        
    Raises:
        HTTPException: If document processing fails or required fields are missing
    """
    handler = DocumentHandler()
    
    try:
        document_dicts = None
        if documents:
            # Validate that all documents have required fields
            for doc in documents:
                if not doc.content:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Document '{doc.name}' must have 'content' field"
                    )
                if not doc.description:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Document '{doc.name}' must have 'description' field"
                    )
            document_dicts = [doc.dict() for doc in documents]
        
        processed_documents = await handler.process_documents(
            documents=document_dicts,
            files=None  # No file uploads for JSON endpoint
        )
        
        return processed_documents, handler
        
    except Exception as e:
        handler.cleanup()
        raise HTTPException(status_code=400, detail=str(e))


class DocumentProcessor:
    """Context manager for handling documents with automatic cleanup."""
    
    def __init__(self, processed_documents: List[Dict], handler: DocumentHandler):
        self.processed_documents = processed_documents
        self.handler = handler
    
    async def __aenter__(self) -> List[Dict]:
        return self.processed_documents
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.handler.cleanup()


async def get_form_document_processor(
    doc_data: Tuple[List[Dict], DocumentHandler] = Depends(process_form_documents)
) -> DocumentProcessor:
    """
    Dependency that returns a DocumentProcessor for form-based documents.
    Use this for endpoints that accept multipart/form-data with file uploads.
    """
    processed_documents, handler = doc_data
    return DocumentProcessor(processed_documents, handler)


async def get_json_document_processor(
    documents: Optional[List[DocumentSpecification]] = None
) -> DocumentProcessor:
    """
    Dependency that returns a DocumentProcessor for JSON-based documents.
    Use this for endpoints that accept pure JSON requests (no file uploads).
    """
    processed_documents, handler = await process_json_documents(documents)
    return DocumentProcessor(processed_documents, handler)
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.services.source_handler import SourceHandler
from rhesis.backend.logging import logger


def get_document_source_type(db: Session, organization_id: str) -> models.TypeLookup:
    """
    Get the Document source type, creating it if it doesn't exist.

    Args:
        db: Database session
        organization_id: Organization ID for tenant context

    Returns:
        TypeLookup: Document source type

    Raises:
        ValueError: If Document source type cannot be found or created
    """
    document_source_type = crud.get_type_lookup_by_name_and_value(
        db, type_name="SourceType", type_value="Document", organization_id=organization_id
    )
    if not document_source_type:
        raise ValueError("Document source type not found. Please ensure database is initialized.")
    return document_source_type


async def upload_and_create_source(
    db: Session,
    file: UploadFile,
    organization_id: str,
    user_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> models.Source:
    """
    Upload a file and create a Source record of type 'Document'.

    This function handles the complete workflow:
    - Validates file and gets Document source type
    - Saves file using SourceHandler
    - Extracts content from the file
    - Creates Source record with metadata and content

    Args:
        db: Database session
        file: The uploaded file
        organization_id: Organization ID for tenant context
        user_id: User ID for tenant context
        title: Optional title for the source (defaults to filename)
        description: Optional description for the source

    Returns:
        Source: Created source record with file metadata and extracted content

    Raises:
        ValueError: If file validation fails or source creation fails
    """
    # Get Document source type
    document_source_type = get_document_source_type(db, organization_id)

    # Initialize SourceHandler (uses cloud storage)
    handler = SourceHandler()

    # Save file and get metadata
    file_metadata = await handler.save_source(
        file=file,
        organization_id=organization_id,
        source_id=str(uuid.uuid4()),  # Generate unique source ID
    )

    # Extract content separately
    extracted_content = None
    try:
        extracted_content = await handler.extract_source_content(file_metadata["file_path"])
    except Exception as e:
        # Log extraction error but don't fail the upload
        logger.warning(f"Failed to extract content from {file.filename}: {str(e)}")

    # Create Source record
    source_data = schemas.SourceCreate(
        title=title or file.filename,
        description=description,
        source_type_id=document_source_type.id,
        source_metadata=file_metadata,  # File metadata (size, hash, path, etc.)
        organization_id=organization_id,
        user_id=user_id,
        content=extracted_content,  # Extracted text content
    )

    # Save to database
    created_source = crud.create_source(
        db=db, source=source_data, organization_id=organization_id, user_id=user_id
    )

    return created_source


def validate_source_for_extraction(
    db: Session, source_id: uuid.UUID, organization_id: str, user_id: str
) -> tuple[models.Source, str]:
    """
    Validate that a source exists and is suitable for content extraction.

    Args:
        db: Database session
        source_id: UUID of the source to validate
        organization_id: Organization ID for tenant context
        user_id: User ID for tenant context

    Returns:
        tuple: (Source model, file_path)

    Raises:
        ValueError: If source validation fails
    """
    # Get the source record
    db_source = crud.get_source(
        db, source_id=source_id, organization_id=organization_id, user_id=user_id
    )
    if db_source is None:
        raise ValueError("Source not found")

    # Validate source type is Document
    if not db_source.source_type_id:
        raise ValueError("Source has no type specified")

    # Get source type details
    source_type = crud.get_type_lookup(
        db, db_source.source_type_id, organization_id=organization_id, user_id=user_id
    )
    if not source_type or source_type.type_value != "Document":
        raise ValueError("Only documents support content extraction.")

    # Check if source has file metadata
    if not db_source.source_metadata or "file_path" not in db_source.source_metadata:
        raise ValueError("Source has no uploaded file")

    file_path = db_source.source_metadata["file_path"]
    return db_source, file_path


async def extract_source_content(
    db: Session, source_id: uuid.UUID, organization_id: str, user_id: str
) -> dict:
    """
    Extract text content from an uploaded source file and update the source record.

    Args:
        db: Database session
        source_id: UUID of the source to extract content from
        organization_id: Organization ID for tenant context
        user_id: User ID for tenant context

    Returns:
        dict: Extraction result with content and metadata

    Raises:
        ValueError: If source validation or extraction fails
    """
    # Validate source
    db_source, file_path = validate_source_for_extraction(db, source_id, organization_id, user_id)

    # Initialize SourceHandler
    handler = SourceHandler()

    # Extract content using SourceHandler
    content = await handler.extract_source_content(file_path)

    # Update the source with extracted content
    update_data = schemas.SourceUpdate(content=content)
    updated_source = crud.update_source(
        db,
        source_id=source_id,
        source=update_data,
        organization_id=organization_id,
        user_id=user_id,
    )

    return {
        "source_id": str(source_id),
        "content": content,
        "format": Path(file_path).suffix.lstrip("."),
        "extracted_at": updated_source.updated_at,
    }


async def get_source_file_content(
    db: Session, source_id: uuid.UUID, organization_id: str, user_id: str
) -> tuple[bytes, str, str]:
    """
    Retrieve the raw file content from storage for a source.

    Args:
        db: Database session
        source_id: UUID of the source to get content from
        organization_id: Organization ID for tenant context
        user_id: User ID for tenant context

    Returns:
        tuple: (file_content, content_type, filename)

    Raises:
        ValueError: If source validation fails
    """
    # Validate source
    db_source, file_path = validate_source_for_extraction(db, source_id, organization_id, user_id)

    # Initialize SourceHandler
    handler = SourceHandler()

    # Get file content
    content = await handler.get_source_content(file_path)

    # Determine content type from file extension
    file_extension = Path(file_path).suffix.lower()
    content_type_map = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    content_type = content_type_map.get(file_extension, "application/octet-stream")

    return content, content_type, Path(file_path).name

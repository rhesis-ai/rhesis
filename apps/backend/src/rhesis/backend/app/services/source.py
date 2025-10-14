import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.services.handlers import get_source_handler
from rhesis.backend.logging import logger


# not only document, but also other source types
# retrieve the source type by id
def get_source_type_by_value(
    db: Session, organization_id: str, source_type_value: str
) -> Optional[models.TypeLookup]:
    """
    Get a specific source type by its value.

    Args:
        db: Database session
        organization_id: Organization ID for tenant context
        source_type_value: The source type value (e.g., "Document", "Website")

    Returns:
        TypeLookup: The source type, or None if not found
    """
    return crud.get_type_lookup_by_name_and_value(
        db, type_name="SourceType", type_value=source_type_value, organization_id=organization_id
    )


async def upload_and_create_source(
    db: Session,
    file: UploadFile,
    organization_id: str,
    user_id: str,
    source_type_value: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> models.Source:
    """
    Upload a file and create a Source record with the specified source type.

    This function handles the complete workflow:
    - Validates file and gets source type
    - Saves file using appropriate handler
    - Extracts content from the file
    - Creates Source record with metadata and content

    Args:
        db: Database session
        file: The uploaded file
        organization_id: Organization ID for tenant context
        user_id: User ID for tenant context
        source_type_value: Type of source (e.g., "Document", "Website") - defaults to "Document"
        title: Optional title for the source (defaults to filename)
        description: Optional description for the source

    Returns:
        Source: Created source record with file metadata and extracted content

    Raises:
        ValueError: If file validation fails or source creation fails
    """
    # Get the specified source type
    source_type = get_source_type_by_value(db, organization_id, source_type_value)
    if not source_type:
        raise ValueError(
            f"Source type '{source_type_value}' not found. Please ensure database is initialized."
        )

    # Initialize handler based on source type
    handler = get_source_handler(source_type_value)

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
        source_type_id=source_type.id,  # Use the dynamic source type
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
    if not source_type:
        raise ValueError("Source type not found.")

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

    # Get source type to determine handler
    source_type = crud.get_type_lookup(
        db, db_source.source_type_id, organization_id=organization_id, user_id=user_id
    )
    if not source_type:
        raise ValueError("Source type not found.")

    # Initialize handler based on source type
    handler = get_source_handler(source_type.type_value)

    # Extract content using handler
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

    # Get source type to determine handler
    source_type = crud.get_type_lookup(
        db, db_source.source_type_id, organization_id=organization_id, user_id=user_id
    )
    if not source_type:
        raise ValueError("Source type not found.")

    # Initialize handler based on source type
    handler = get_source_handler(source_type.type_value)

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

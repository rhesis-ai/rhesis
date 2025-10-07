import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.document_handler import DocumentHandler
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header

router = APIRouter(
    prefix="/sources",
    tags=["sources"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Source)
@handle_database_exceptions(
    entity_name="source", custom_unique_message="Source with this name already exists"
)
def create_source(
    source: schemas.SourceCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create source with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_source(
        db=db, source=source, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.Source])
@with_count_header(model=models.Source)
def read_sources(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all sources with their related objects"""
    organization_id, user_id = tenant_context
    return crud.get_sources(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{source_id}")
def read_source(
    source_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get source with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_source = crud.get_source(
        db, source_id=source_id, organization_id=organization_id, user_id=user_id
    )
    if db_source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return db_source


@router.delete("/{source_id}")
def delete_source(
    source_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete source with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_source = crud.delete_source(
        db, source_id=source_id, organization_id=organization_id, user_id=user_id
    )
    if db_source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return db_source


@router.put("/{source_id}", response_model=schemas.Source)
def update_source(
    source_id: uuid.UUID,
    source: schemas.SourceUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update source with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_source = crud.update_source(
        db, source_id=source_id, source=source, organization_id=organization_id, user_id=user_id
    )
    if db_source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return db_source


@router.post("/upload/", response_model=schemas.Source)
async def upload_source(
    file: UploadFile = File(...),
    title: str = None,
    description: str = None,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Upload a file and create a Source record of type 'Document'.

    This endpoint combines file upload with Source creation:
    - Saves the file using DocumentHandler
    - Creates a Source record with Document source_type_id
    - Populates source_metadata with file information

    Args:
        file: The uploaded file
        title: Optional title for the source (defaults to filename)
        description: Optional description for the source
        db: Database session
        tenant_context: Tenant context containing organization_id and user_id
        current_user: Current authenticated user

    Returns:
        schemas.Source: Created source record with file metadata

    Raises:
        HTTPException: If file upload fails or source creation fails
    """
    organization_id, user_id = tenant_context

    try:
        # Get Document source type
        document_source_type = crud.get_type_lookup_by_name_and_value(
            db, type_name="SourceType", type_value="Document", organization_id=organization_id
        )
        if not document_source_type:
            raise HTTPException(
                status_code=500,
                detail="Document source type not found. Please ensure database is initialized.",
            )

        # Initialize DocumentHandler
        handler = DocumentHandler()

        # Save file and get metadata
        metadata = await handler.save_document(
            document=file,
            organization_id=str(organization_id),
            source_id=str(uuid.uuid4()),  # Generate unique source ID
        )

        # Create Source record
        source_data = schemas.SourceCreate(
            title=title or file.filename,
            description=description,
            source_type_id=document_source_type.id,
            source_metadata=metadata,
            organization_id=organization_id,
            user_id=user_id,
        )

        # Save to database
        created_source = crud.create_source(
            db=db, source=source_data, organization_id=organization_id, user_id=user_id
        )

        return created_source

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload source: {str(e)}")


@router.post("/{source_id}/extract")
async def extract_source_content(
    source_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Extract text content from an uploaded source file.

    This endpoint:
    - Validates the source is of type 'Document'
    - Retrieves the file from storage
    - Extracts text content using DocumentExtractor
    - Updates the Source record with extracted content

    Args:
        source_id: UUID of the source to extract content from
        db: Database session
        tenant_context: Tenant context containing organization_id and user_id
        current_user: Current authenticated user

    Returns:
        dict: Extraction result with content and metadata

    Raises:
        HTTPException: If source not found, not a document type, or extraction fails
    """
    organization_id, user_id = tenant_context

    try:
        # Get the source record
        db_source = crud.get_source(
            db, source_id=source_id, organization_id=organization_id, user_id=user_id
        )
        if db_source is None:
            raise HTTPException(status_code=404, detail="Source not found")

        # Validate source type is Document
        if not db_source.source_type_id:
            raise HTTPException(status_code=400, detail="Source has no type specified")

        # Get source type details
        source_type = crud.get_type_lookup(
            db, db_source.source_type_id, organization_id=organization_id, user_id=user_id
        )
        if not source_type or source_type.type_value != "Document":
            raise HTTPException(
                status_code=400,
                detail="Only documents support content extraction.",
            )

        # Check if source has file metadata
        if not db_source.source_metadata or "file_path" not in db_source.source_metadata:
            raise HTTPException(status_code=400, detail="Source has no uploaded file")

        file_path = db_source.source_metadata["file_path"]

        # Initialize DocumentHandler
        handler = DocumentHandler()

        # Extract content using DocumentHandler
        content = await handler.extract_document_content(file_path)

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

    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="Source file not found. Please check the file path."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract content: {str(e)}")


@router.get("/{source_id}/content")
async def get_source_content(
    source_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Retrieve the raw file content from storage.

    This endpoint:
    - Validates the source is of type 'Document'
    - Gets the file path from the Source record
    - Retrieves the raw file content from storage
    - Returns the content as a streaming response

    Args:
        source_id: UUID of the source to get content from
        db: Database session
        tenant_context: Tenant context containing organization_id and user_id
        current_user: Current authenticated user

    Returns:
        StreamingResponse: Raw file content

    Raises:
        HTTPException: If source not found, not a document type, or file retrieval fails
    """
    organization_id, user_id = tenant_context

    try:
        # Get the source record
        db_source = crud.get_source(
            db, source_id=source_id, organization_id=organization_id, user_id=user_id
        )
        if db_source is None:
            raise HTTPException(status_code=404, detail="Source not found")

        # Validate source type is Document
        if not db_source.source_type_id:
            raise HTTPException(status_code=400, detail="Source has no type specified")

        # Get source type details
        source_type = crud.get_type_lookup(
            db, db_source.source_type_id, organization_id=organization_id, user_id=user_id
        )
        if not source_type or source_type.type_value != "Document":
            raise HTTPException(
                status_code=400,
                detail="Source is not a document type. Only documents supported.",
            )

        # Check if source has file metadata
        if not db_source.source_metadata or "file_path" not in db_source.source_metadata:
            raise HTTPException(status_code=400, detail="Source has no uploaded file")

        file_path = db_source.source_metadata["file_path"]

        # Initialize DocumentHandler
        handler = DocumentHandler()

        # Get file content
        content = await handler.get_document_content(file_path)

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

        # Return as streaming response
        return StreamingResponse(
            iter([content]),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={Path(file_path).name}",
                "Content-Length": str(len(content)),
            },
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="Source file not found. Please check the file path."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve source content: {str(e)}")

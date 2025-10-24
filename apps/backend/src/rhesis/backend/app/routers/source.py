import urllib.parse
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.source import (
    extract_source_content,
    get_source_file_content,
    upload_and_create_source,
)
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


@router.post("/upload", response_model=schemas.Source)
async def upload_source(
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Upload a file and create a Source record of type 'Document'.

    This endpoint combines file upload with Source creation:
    - Saves the file using Document handler
    - Creates a Source record with Document source_type_id
    - Populates source_metadata with file information
    - Extracts content from the uploaded file

    Note: Currently only supports Document type. Other source types (Website, API,
    Database, Code, Manual) can be created via the regular POST /sources/ endpoint.

    Args:
        file: The uploaded file
        title: Optional title for the source (defaults to filename)
        description: Optional description for the source
        db: Database session
        tenant_context: Tenant context containing organization_id and user_id
        current_user: Current authenticated user

    Returns:
        schemas.Source: Created source record with file metadata and extracted content

    Raises:
        HTTPException: If file upload fails or source creation fails
    """
    organization_id, user_id = tenant_context

    try:
        return await upload_and_create_source(
            db=db,
            file=file,
            organization_id=str(organization_id),
            user_id=str(user_id),
            source_type_value="Document",  # Default to Document for file uploads
            title=title,
            description=description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload source: {str(e)}")


@router.post("/{source_id}/extract")
async def extract_source_content_endpoint(
    source_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Extract text content from an uploaded source file.

    This endpoint:
    - Validates the source has a supported source type
    - Retrieves the file from storage (for Document types)
    - Extracts text content using the appropriate handler
    - Updates the Source record with extracted content

    Args:
        source_id: UUID of the source to extract content from
        db: Database session
        tenant_context: Tenant context containing organization_id and user_id
        current_user: Current authenticated user

    Returns:
        dict: Extraction result with content and metadata

    Raises:
        HTTPException: If source not found, unsupported source type, or extraction fails
    """
    organization_id, user_id = tenant_context

    try:
        return await extract_source_content(
            db=db,
            source_id=source_id,
            organization_id=str(organization_id),
            user_id=str(user_id),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract content: {str(e)}")
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="Source file not found. Please check the file path."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract content: {str(e)}")


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
    - Validates the source has a supported source type
    - Gets the file path from the Source record (for Document types)
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
        HTTPException: If source not found, unsupported source type, or file retrieval fails
    """
    organization_id, user_id = tenant_context

    try:
        content, content_type, filename = await get_source_file_content(
            db=db,
            source_id=source_id,
            organization_id=str(organization_id),
            user_id=str(user_id),
        )

        # Return as streaming response
        return StreamingResponse(
            iter([content]),
            media_type=content_type,
            headers={
                "Content-Disposition": (
                    f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}"
                ),
                "Content-Length": str(len(content)),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="Source file not found. Please check the file path."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve source content: {str(e)}")

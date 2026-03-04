"""File management API router.

Provides endpoints for uploading, downloading, and managing binary file
attachments associated with Tests (input files) and TestResults (output files).
"""

import uuid
from io import BytesIO
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.file import FileEntityType

router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}},
)

# Size limits
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB per file
MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 20 MB total per entity
MAX_FILES_PER_REQUEST = 10

# Allowed MIME type prefixes
ALLOWED_MIME_PREFIXES = ("image/", "application/pdf", "audio/")


def _validate_mime_type(content_type: str) -> None:
    """Validate that the MIME type is allowed."""
    if not any(content_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=422,
            detail=(
                f"File type '{content_type}' is not allowed. "
                f"Allowed types: images, PDFs, and audio files."
            ),
        )


@router.post("/", response_model=List[schemas.FileResponse])
async def upload_files(
    files: List[UploadFile] = File(...),
    entity_id: uuid.UUID = Query(..., description="ID of the entity to attach files to"),
    entity_type: FileEntityType = Query(..., description="Type of entity (Test or TestResult)"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Upload one or more files and attach them to a Test or TestResult."""
    organization_id, user_id = tenant_context

    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {MAX_FILES_PER_REQUEST} files per request.",
        )

    # Check existing total size for this entity
    existing_total = crud.get_entity_files_total_size(
        db, entity_id, entity_type.value, organization_id
    )

    # Determine starting position for append semantics
    max_position = (
        db.query(func.coalesce(func.max(models.File.position), -1))
        .filter(
            models.File.entity_id == entity_id,
            models.File.entity_type == entity_type.value,
            models.File.deleted_at.is_(None),
        )
        .scalar()
    )
    next_position = max_position + 1

    created_files = []
    upload_total = 0

    for idx, file in enumerate(files):
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required.")

        content_type = file.content_type or "application/octet-stream"
        _validate_mime_type(content_type)

        file_bytes = await file.read()
        file_size = len(file_bytes)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        if file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"File '{file.filename}' is too large ({file_size} bytes). "
                    f"Maximum size per file is {MAX_FILE_BYTES} bytes."
                ),
            )

        upload_total += file_size
        if existing_total + upload_total > MAX_TOTAL_BYTES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Total file size for this entity would exceed {MAX_TOTAL_BYTES} bytes limit."
                ),
            )

        file_data = schemas.FileCreate(
            filename=file.filename,
            content_type=content_type,
            size_bytes=file_size,
            content=file_bytes,
            entity_id=entity_id,
            entity_type=entity_type,
            position=next_position + idx,
        )

        db_file = crud.create_file(db, file_data, organization_id=organization_id, user_id=user_id)
        created_files.append(db_file)

    return created_files


@router.get("/{file_id}", response_model=schemas.FileResponse)
def get_file_metadata(
    file_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get file metadata (does not include file content)."""
    organization_id, user_id = tenant_context
    db_file = crud.get_file(db, file_id, organization_id, user_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file


@router.get("/{file_id}/content")
def download_file_content(
    file_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Download file content as binary with correct Content-Type."""
    organization_id, user_id = tenant_context
    db_file = crud.get_file_with_content(db, file_id, organization_id, user_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    if not db_file.content:
        raise HTTPException(status_code=404, detail="File content not found")

    return StreamingResponse(
        BytesIO(db_file.content),
        media_type=db_file.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{db_file.filename}"',
            "Content-Length": str(db_file.size_bytes),
        },
    )


@router.delete("/{file_id}", response_model=schemas.FileResponse)
def delete_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Soft-delete a file."""
    organization_id, user_id = tenant_context
    db_file = crud.delete_file(db, file_id, organization_id, user_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file

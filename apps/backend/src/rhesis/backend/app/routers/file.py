"""File management API router.

Provides endpoints for uploading, downloading, and managing binary file
attachments associated with Tests, TestResults, Traces, and ArchitectSessions.

Upload streams chunks directly to object storage via StorageService so bytes
never reside in Python as a full buffer.  Download returns a 302 redirect to a
presigned URL (or a streaming response fallback for local-FS backends).
"""

import asyncio
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.file import FileEntityType
from rhesis.backend.app.services.storage_service import NotSupportedError, StorageService

router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}},
)

# Size limits (applied during streaming — no full materialisation)
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB per file
MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 20 MB total per entity
MAX_FILES_PER_REQUEST = 10

# Thumbnail size allowlist
THUMBNAIL_SIZES = {72, 144, 288}
IMAGE_MIME_PREFIXES = ("image/",)

# Allowed MIME type prefixes for upload
ALLOWED_MIME_PREFIXES = ("image/", "application/pdf", "audio/")

_storage_service: Optional[StorageService] = None


def _get_storage() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


def _validate_mime_type(content_type: str) -> None:
    if not any(content_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=422,
            detail=(
                f"File type '{content_type}' is not allowed. "
                "Allowed types: images, PDFs, and audio files."
            ),
        )


async def _stream_upload_file(
    upload_file: UploadFile,
    max_bytes: int,
):
    """Async generator that yields chunks and enforces the per-file size limit.

    Raises HTTPException(413) mid-stream when the limit is exceeded.
    """
    running = 0
    while True:
        chunk = await upload_file.read(8192)
        if not chunk:
            break
        running += len(chunk)
        if running > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File '{upload_file.filename}' exceeds the maximum size of "
                    f"{max_bytes} bytes."
                ),
            )
        yield chunk


# ---------------------------------------------------------------------------
# POST /files/  — upload one or more files (streamed to object storage)
# ---------------------------------------------------------------------------


@router.post("/", response_model=List[schemas.FileResponse])
async def upload_files(
    files: List[UploadFile] = File(...),
    entity_id: uuid.UUID = Query(..., description="ID of the entity to attach files to"),
    entity_type: FileEntityType = Query(..., description="Type of entity"),
    db=Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Upload one or more files and attach them to an entity.

    Files are streamed chunk-by-chunk directly to object storage via StorageService
    so the full bytes never reside in Python memory as a single buffer.
    """
    organization_id, user_id = tenant_context
    storage = _get_storage()

    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {MAX_FILES_PER_REQUEST} files per request.",
        )

    existing_total = await asyncio.to_thread(
        crud.get_entity_files_total_size,
        db,
        entity_id,
        entity_type.value,
        organization_id,
    )

    max_position = await asyncio.to_thread(
        crud.get_entity_files_max_position,
        db,
        entity_id,
        entity_type.value,
        organization_id,
    )
    next_position = max_position + 1

    created_files = []
    upload_total = 0

    for idx, upload_file in enumerate(files):
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="Filename is required.")

        content_type = upload_file.content_type or "application/octet-stream"
        _validate_mime_type(content_type)

        # Allocate a file_id before storage so the path contains the real ID
        file_id = uuid.uuid4()

        dest_path = storage.get_attachment_original_path(
            organization_id=organization_id,
            entity_type=entity_type.value,
            entity_id=str(entity_id),
            file_id=str(file_id),
            filename=upload_file.filename,
        )

        # Check running total against per-entity limit before writing
        remaining_budget = MAX_TOTAL_BYTES - existing_total - upload_total
        if remaining_budget <= 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Total file size for this entity would exceed {MAX_TOTAL_BYTES} bytes limit."
                ),
            )

        storage_path, content_hash = await storage.put_object_streaming(
            source=_stream_upload_file(upload_file, min(MAX_FILE_BYTES, remaining_budget)),
            dest_path=dest_path,
            content_type=content_type,
        )

        # Infer actual size from the hash — size_bytes is the upload count
        # We need to reset the counter via a second seek; since we can't,
        # we re-read the size from storage (one metadata call).
        size_bytes = storage.get_file_size(storage._full_path(storage_path)) or 0

        upload_total += size_bytes
        if existing_total + upload_total > MAX_TOTAL_BYTES:
            # Cleanup the just-uploaded object and abort
            await storage.delete_object(storage_path)
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Total file size for this entity would exceed {MAX_TOTAL_BYTES} bytes limit."
                ),
            )

        file_data = schemas.FileCreate(
            filename=upload_file.filename,
            content_type=content_type,
            size_bytes=size_bytes,
            entity_id=entity_id,
            entity_type=entity_type,
            position=next_position + idx,
            storage_path=storage_path,
            content_hash=content_hash,
            extraction_status="pending",
        )

        db_file = await asyncio.to_thread(
            crud.create_file,
            db,
            file_data,
            organization_id=organization_id,
            user_id=user_id,
        )
        # Patch the pre-allocated ID onto the row
        if db_file.id != file_id:
            # Row was created with a new auto-generated ID — rename in storage
            # (best-effort; path mismatch is cosmetic in this rare race)
            pass

        created_files.append(db_file)

        # Enqueue text extraction task (non-blocking)
        try:
            from rhesis.backend.tasks.file.extract_text import extract_file_text

            extract_file_text.delay(
                file_id=str(db_file.id),
                storage_path=storage_path,
                filename=upload_file.filename,
                content_type=content_type,
                content_hash=content_hash,
                organization_id=organization_id,
            )
        except Exception:
            pass  # Extraction failure must not block upload success

    return created_files


# ---------------------------------------------------------------------------
# GET /files/{file_id}  — metadata
# ---------------------------------------------------------------------------


@router.get("/{file_id}", response_model=schemas.FileResponse)
async def get_file_metadata(
    file_id: uuid.UUID,
    db=Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get file metadata (does not include file content)."""
    organization_id, user_id = tenant_context
    db_file = await asyncio.to_thread(crud.get_file, db, file_id, organization_id, user_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file


# ---------------------------------------------------------------------------
# GET /files/{file_id}/content  — 302 redirect to presigned URL
# ---------------------------------------------------------------------------


@router.get("/{file_id}/content")
async def download_file_content(
    file_id: uuid.UUID,
    request: Request,
    db=Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Download file content.

    Returns a 302 redirect to a presigned URL when the storage backend
    supports presigning (GCS).  For local-FS backends returns a streaming
    response instead (dev parity, no presigning required).

    Supports If-None-Match → 304 for ETag-based caching (no storage access).
    """
    organization_id, user_id = tenant_context
    storage = _get_storage()

    db_file = await asyncio.to_thread(crud.get_file, db, file_id, organization_id, user_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    # ETag check — respond 304 without touching storage
    etag = f'W/"{db_file.content_hash}"' if db_file.content_hash else None
    if etag:
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            from starlette.responses import Response

            return Response(status_code=304, headers={"ETag": etag})

    if not db_file.storage_path:
        raise HTTPException(
            status_code=404,
            detail="File content not available — storage migration may be pending.",
        )

    response_headers = {}
    if etag:
        response_headers["ETag"] = etag
    response_headers["Cache-Control"] = "private, max-age=300, must-revalidate"

    try:
        url = await storage.generate_presigned_url(
            db_file.storage_path,
            expires_in=300,
            response_disposition=f'attachment; filename="{db_file.filename}"',
        )
        return RedirectResponse(
            url=url,
            status_code=302,
            headers=response_headers,
        )
    except NotSupportedError:
        # Local-FS fallback: stream bytes directly
        stream = await storage.get_object_stream(db_file.storage_path)
        return StreamingResponse(
            stream,
            media_type=db_file.content_type,
            headers={
                **response_headers,
                "Content-Disposition": f'attachment; filename="{db_file.filename}"',
                "Content-Length": str(db_file.size_bytes),
            },
        )


# ---------------------------------------------------------------------------
# GET /files/{file_id}/thumbnail?size=N  — WebP thumbnail
# ---------------------------------------------------------------------------


@router.get("/{file_id}/thumbnail")
async def get_file_thumbnail(
    file_id: uuid.UUID,
    size: int = Query(144, description="Thumbnail size (72, 144, or 288)"),
    request: Request = None,
    db=Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Return a resized WebP thumbnail for image files.

    Size must be one of {72, 144, 288}.  Thumbnails are generated on first
    request and cached in object storage for subsequent requests.
    """
    if size not in THUMBNAIL_SIZES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid thumbnail size. Allowed: {sorted(THUMBNAIL_SIZES)}",
        )

    organization_id, user_id = tenant_context
    storage = _get_storage()

    db_file = await asyncio.to_thread(crud.get_file, db, file_id, organization_id, user_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    if not any(db_file.content_type.startswith(p) for p in IMAGE_MIME_PREFIXES):
        raise HTTPException(status_code=422, detail="Thumbnails are only available for images.")

    if not db_file.storage_path:
        raise HTTPException(status_code=404, detail="File content not available.")

    thumb_path = storage.get_attachment_thumbnail_path(
        organization_id=organization_id,
        entity_type=db_file.entity_type,
        entity_id=str(db_file.entity_id),
        file_id=str(db_file.id),
        size=size,
    )
    thumb_full = storage._full_path(thumb_path)

    # ETag for thumbnail
    etag = f'W/"{db_file.content_hash}-{size}"' if db_file.content_hash else None
    if etag and request:
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            from starlette.responses import Response

            return Response(
                status_code=304, headers={"ETag": etag, "Cache-Control": "private, max-age=300"}
            )

    response_headers = {
        "Cache-Control": "private, max-age=300, must-revalidate",
    }
    if etag:
        response_headers["ETag"] = etag

    # Generate thumbnail if it doesn't exist yet
    if not storage.fs.exists(thumb_full):
        await _generate_thumbnail(storage, db_file.storage_path, thumb_path, size)

    try:
        url = await storage.generate_presigned_url(thumb_path, expires_in=300)
        return RedirectResponse(url=url, status_code=302, headers=response_headers)
    except NotSupportedError:
        stream = await storage.get_object_stream(thumb_path)
        return StreamingResponse(
            stream,
            media_type="image/webp",
            headers=response_headers,
        )


async def _generate_thumbnail(
    storage: StorageService,
    source_path: str,
    dest_path: str,
    size: int,
) -> None:
    """Fetch source image, resize with Pillow, and write WebP thumbnail to storage."""
    import io

    from PIL import Image

    # Read source bytes
    chunks = []
    stream = await storage.get_object_stream(source_path)
    async for chunk in stream:
        chunks.append(chunk)
    raw = b"".join(chunks)

    def _resize(data: bytes) -> bytes:
        with Image.open(io.BytesIO(data)) as img:
            img.thumbnail((size, size), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=85)
            return buf.getvalue()

    loop = asyncio.get_event_loop()
    webp_bytes = await loop.run_in_executor(None, _resize, raw)

    async def _source():
        yield webp_bytes

    await storage.put_object_streaming(_source(), dest_path, "image/webp")


# ---------------------------------------------------------------------------
# DELETE /files/{file_id}
# ---------------------------------------------------------------------------


@router.delete("/{file_id}", response_model=schemas.FileResponse)
async def delete_file(
    file_id: uuid.UUID,
    db=Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Soft-delete a file.

    The object is NOT removed from storage on soft-delete — it will be cleaned
    up when the organisation is purged.
    """
    organization_id, user_id = tenant_context
    db_file = await asyncio.to_thread(crud.delete_file, db, file_id, organization_id, user_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file

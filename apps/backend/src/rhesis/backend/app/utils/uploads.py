"""Shared upload plumbing: read a capped body, write it to object storage.

Every feature that accepts a file does the same two things before it can do
anything interesting — bound the body so one request cannot exhaust the worker,
and put the bytes somewhere, turning a storage failure into an answer the
caller can act on. That was reimplemented per feature (knowledge sources in
``services/handlers/document.py``, attachments in ``routers/file.py``, the
OWASP cache, branding assets), each with its own limit check and its own idea
of what a storage error means.

Lives in ``app/utils/`` rather than under one service because the callers are
unrelated to each other; see the backend AGENTS.md rule.

Storage itself is not re-abstracted here: :class:`StorageService` is the one
place that knows about ``gs://``/``s3://``/``file://``, and every path builder
(``get_source_path``, ``get_attachment_original_path``, ``get_branding_path``)
stays on it. This module is only the request-shaped wrapper around it.
"""

import logging

from fastapi import HTTPException, UploadFile

from rhesis.backend.app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


async def read_upload_capped(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    """Read an upload fully, refusing anything over ``max_bytes``.

    Reads one byte past the limit rather than the whole body, so an oversized
    upload is rejected without first being held in memory.

    Args:
        upload: the incoming file
        max_bytes: hard limit, inclusive
        label: what to call it in the error ("Favicon", "Font file for weight 400")

    Raises:
        HTTPException: 413 when over the limit, 400 when empty
    """
    content = await upload.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"{label} exceeds the maximum size of {max_bytes} bytes.",
        )
    if not content:
        raise HTTPException(status_code=400, detail=f"{label} is empty.")
    return content


def store_bytes(
    storage: StorageService,
    content: bytes,
    dest_path: str,
    content_type: str,
) -> tuple:
    """Write ``content`` to ``dest_path``, returning ``(stored_path, sha256)``.

    Turns a storage failure into a 503 naming the setting to fix. Unwritable
    storage is a deployment problem, not a bad request, and the local path is
    easy to get wrong — it is a path inside the container under
    docker-compose and a host directory when the backend runs directly. The
    raw ``OSError`` surfaced as a 500 whose traceback ended in ``mkdir``
    rather than anything pointing at ``STORAGE_SERVICE_URI``.

    Caught broadly because writes go through fsspec, and its cloud backends
    (gcsfs, s3fs, ...) raise their own native exception types.
    """
    try:
        return storage.put_object_bytes(content, dest_path, content_type)
    except Exception as e:  # noqa: BLE001 — fsspec backends raise native types
        logger.error(f"Could not write {dest_path} to storage: {e}")
        raise HTTPException(
            status_code=503,
            detail=(
                "Storage is not writable, so the upload could not be saved. "
                "Check STORAGE_SERVICE_URI and that its location exists."
            ),
        ) from e

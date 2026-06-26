"""Polymorphic file-shape compatibility helpers.

Penelope receives file attachments in two shapes:

* **Backend execution pipeline (post file-storage migration):**
  :class:`rhesis.sdk.connector.types.FileReference` Pydantic models — bytes
  live in object storage; the model carries metadata (``filename``,
  ``content_type``, ``extracted_text``, ``storage_path`` …).
* **Chatbot / architect / legacy tests:** plain ``dict`` objects with
  optional ``data`` (base64-encoded bytes).

We deliberately **do not** coerce ``FileReference`` to ``dict`` at the
penelope boundary, because the backend endpoint service uses
``isinstance(f, FileReference)`` to decide whether to materialise bytes
from storage on-demand. Collapsing to ``dict`` here silently routes the
request through the legacy "extract from inline base64" path and breaks
file delivery for endpoints that support file attachments.

Two small helpers handle the two places we need to talk to both shapes:

* :func:`file_attr` — read a metadata field from either shape (used when
  building prompt context strings).
* :func:`json_default` — a ``json.dumps`` ``default=`` fallback that
  serialises Pydantic models so we can log tool-call arguments without
  destroying the live ``FileReference`` instances in the action params.
"""

import base64
from typing import Any, Optional, Tuple


def file_attr(f: Any, key: str, default: Any = "") -> Any:
    """Read ``key`` from a file attachment regardless of its concrete shape."""
    if isinstance(f, dict):
        return f.get(key, default)
    return getattr(f, key, default)


def file_extracted_text(f: Any) -> Optional[str]:
    """Return pre-extracted text for a file attachment, if available.

    Only ``FileReference`` carries this (populated by the backend's text
    extraction pipeline). Plain dict attachments never have it, so this
    returns ``None`` for them.
    """
    return file_attr(f, "extracted_text", None)


def file_bytes_and_type(f: Any) -> Tuple[bytes, str]:
    """Materialize raw bytes and content_type for a file attachment.

    Works for either shape: a dict with inline base64 ``data``, or a
    ``FileReference`` whose bytes live in object storage and are fetched
    on-demand via ``read_bytes()`` (blocking I/O - do not call from an
    asyncio event loop, use :func:`afile_bytes_and_type` instead).
    """
    content_type = file_attr(f, "content_type") or "application/octet-stream"
    if isinstance(f, dict):
        return base64.b64decode(f["data"]), content_type
    return f.read_bytes(), content_type


async def afile_bytes_and_type(f: Any) -> Tuple[bytes, str]:
    """Async sibling of :func:`file_bytes_and_type`.

    Uses ``FileReference.aread_bytes()`` so materializing object-storage
    attachments doesn't block the event loop.
    """
    content_type = file_attr(f, "content_type") or "application/octet-stream"
    if isinstance(f, dict):
        return base64.b64decode(f["data"]), content_type
    return await f.aread_bytes(), content_type


def json_default(obj: Any) -> Any:
    """JSON encoder fallback that dumps Pydantic models to plain dicts.

    Used by the executor to serialise tool-call arguments for the
    conversation log. Only affects the **logged** representation —
    callers continue to see the original Pydantic instances in the live
    ``action_params`` dict that runs the tool.
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

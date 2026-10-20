"""Attachment processing for the Architect agent pipeline.

Decodes base64 file payloads and extracts text so the agent can reason
about file content without holding raw binary in memory.

The output dict shape (``filename`` / ``content_type`` / ``extracted_text``)
matches the shape produced by
:func:`rhesis.backend.app.services.endpoint.files.enrich_files_with_extraction`
and consumed by
:func:`rhesis.backend.app.services.endpoint.files.inject_file_content_into_input`,
so file payloads are interchangeable across the architect, playground,
and test-execution paths.
"""

import logging
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


def without_file_data(attachments: Any) -> Any:
    """The attachments as stored on a message: each file's details, not its bytes.

    The base64 upload is only needed to extract the text in its own turn. Later
    turns read ``extracted_text`` and the UI shows the name and size. Anything not
    shaped like an upload is client JSON this can't judge, so it passes unchanged.
    """
    if not isinstance(attachments, dict):
        return attachments
    files = attachments.get("files")
    if not isinstance(files, list):
        return attachments
    stored = [
        {k: v for k, v in f.items() if k != "data"} if isinstance(f, dict) else f for f in files
    ]
    return {**attachments, "files": stored}


def session_documents(messages: Iterable[Any]) -> List[Dict[str, str]]:
    """Files attached to the session's user messages, as ``{filename, text}``, oldest first.

    The messages are the one record of what was uploaded; the agent gets these each
    turn so a file from an earlier turn can still be read. A file whose text has not
    been written back yet (this turn's, or one uploaded before this existed) is skipped.
    """
    documents = []
    for message in messages:
        if message.role != "user":
            continue
        for f in (message.attachments or {}).get("files") or []:
            text = f.get("extracted_text")
            if text:
                documents.append({"filename": f.get("filename", "file"), "text": text})
    return documents


def process_attachments(
    attachments: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Process raw attachments from the WebSocket payload.

    - ``mentions`` are passed through as-is (already resolved by the frontend).
    - ``files`` have their base64 ``data`` decoded and text extracted via
      ``extract_with_vision_fallback``: text-layer extraction first, then a
      vision-model fallback for image-heavy documents when a model is available.
      The binary ``data`` field is replaced with an ``extracted_text`` string.
      A file that already carries ``extracted_text`` keeps it. One that yielded no
      text gets a note saying so, for this turn only; it is never stored.
    """
    if not attachments:
        return None

    result: Dict[str, Any] = {}

    mentions = attachments.get("mentions")
    if mentions:
        result["mentions"] = mentions

    files = attachments.get("files")
    if files:
        import base64

        from rhesis.sdk.services.extractor import extract_with_vision_fallback

        processed_files = []
        for f in files:
            filename = f.get("filename", "file")
            content_type = f.get("content_type", "")
            if "extracted_text" in f:
                extracted_text = f["extracted_text"] or f"[Could not extract text from {filename}]"
            else:
                try:
                    raw_bytes = base64.b64decode(f.get("data", ""))
                    extracted_text = extract_with_vision_fallback(raw_bytes, filename, content_type)
                except Exception as exc:
                    logger.warning("Failed to extract text from %s: %s", filename, exc)
                    extracted_text = f"[Could not extract text from {filename}: {exc}]"
            processed_files.append(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "extracted_text": extracted_text,
                }
            )
        result["files"] = processed_files

    return result if result else None

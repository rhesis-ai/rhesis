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
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def process_attachments(
    attachments: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Process raw attachments from the WebSocket payload.

    - ``mentions`` are passed through as-is (already resolved by the frontend).
    - ``files`` have their base64 ``data`` decoded and text extracted via
      ``extract_with_vision_fallback``: text-layer extraction first, then a
      vision-model fallback for image-heavy documents when a model is available.
      The binary ``data`` field is replaced with an ``extracted_text`` string.
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

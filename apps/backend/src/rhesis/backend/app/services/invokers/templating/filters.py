"""Jinja2 filters for transforming files to provider-specific content formats."""

import json
from typing import Any, Dict, List, Optional


def to_anthropic(files: Optional[List[Dict[str, Any]]]) -> str:
    """Transform files to Anthropic content blocks.

    Images -> {"type": "image", "source": {"type": "base64", ...}}
    PDFs   -> {"type": "document", "source": {"type": "base64", ...}}
    """
    content = []
    for f in files or []:
        content_type = f.get("content_type", "application/octet-stream")
        block_type = "document" if content_type == "application/pdf" else "image"
        content.append(
            {
                "type": block_type,
                "source": {
                    "type": "base64",
                    "media_type": content_type,
                    "data": f.get("data", ""),
                },
            }
        )
    return json.dumps(content)


def to_openai(files: Optional[List[Dict[str, Any]]]) -> str:
    """Transform files to OpenAI content blocks.

    Each file -> {"type": "image_url", "image_url": {"url": "data:...;base64,..."}}
    """
    content = []
    for f in files or []:
        ct = f.get("content_type", "application/octet-stream")
        data = f.get("data", "")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{ct};base64,{data}"},
            }
        )
    return json.dumps(content)


def to_gemini(files: Optional[List[Dict[str, Any]]]) -> str:
    """Transform files to Google Gemini inline_data parts.

    Each file -> {"inline_data": {"mime_type": "...", "data": "..."}}
    """
    parts = []
    for f in files or []:
        parts.append(
            {
                "inline_data": {
                    "mime_type": f.get("content_type", "application/octet-stream"),
                    "data": f.get("data", ""),
                },
            }
        )
    return json.dumps(parts)


FILE_FILTERS = {
    "to_anthropic": to_anthropic,
    "to_openai": to_openai,
    "to_gemini": to_gemini,
}

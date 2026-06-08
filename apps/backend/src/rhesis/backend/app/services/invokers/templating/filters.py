"""Jinja2 filters for transforming files to provider-specific content formats.

Filters return Python objects (list[dict]) so they compose correctly with
Jinja's built-in ``|tojson`` filter when templates need JSON serialization.
"""

from typing import Any, Dict, List, Optional


def to_anthropic(
    files: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
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
    return content


def to_openai(
    files: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Transform files to OpenAI content blocks.

    Each file -> {"type": "image_url", "image_url": {"url": "data:…;base64,…"}}
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
    return content


def to_gemini(
    files: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Transform files to Google Gemini inline_data parts.

    Each file -> {"inline_data": {"mime_type": "…", "data": "…"}}
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
    return parts


def gemini_parts(
    files: Optional[List[Dict[str, Any]]],
    input_text: str = "",
) -> List[Dict[str, Any]]:
    """Build a Gemini parts array merging a text part with file inline_data parts.

    Usage: {{ files | gemini_parts(input) | tojson }}
    """
    parts: List[Dict[str, Any]] = [{"text": input_text}]
    parts.extend(to_gemini(files))
    return parts


def openai_content(
    files: Optional[List[Dict[str, Any]]],
    input_text: str = "",
) -> List[Dict[str, Any]]:
    """Build an OpenAI content array merging a text block with image_url blocks.

    Usage: {{ files | openai_content(input) | tojson }}
    """
    content: List[Dict[str, Any]] = [{"type": "text", "text": input_text}]
    content.extend(to_openai(files))
    return content


def anthropic_content(
    files: Optional[List[Dict[str, Any]]],
    input_text: str = "",
) -> List[Dict[str, Any]]:
    """Build an Anthropic content array merging a text block with image/document blocks.

    Usage: {{ files | anthropic_content(input) | tojson }}
    """
    content: List[Dict[str, Any]] = [{"type": "text", "text": input_text}]
    content.extend(to_anthropic(files))
    return content


FILE_FILTERS = {
    "to_anthropic": to_anthropic,
    "to_openai": to_openai,
    "to_gemini": to_gemini,
    "gemini_parts": gemini_parts,
    "openai_content": openai_content,
    "anthropic_content": anthropic_content,
}

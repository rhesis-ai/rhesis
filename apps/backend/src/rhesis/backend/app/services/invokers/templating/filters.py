"""Jinja2 filters for transforming files to provider-specific content formats.

Filters return Python objects (list[dict]) so they compose correctly with
Jinja's built-in ``|tojson`` filter when templates need JSON serialization.

All multi-modal filters accept an optional ``input_text`` argument.  When
omitted the filter reads ``input`` from the active Jinja2 template context,
so ``{{ files | gemini_parts | tojson }}`` works without explicitly passing
the input variable.
"""

from typing import Any, Dict, List, Optional

from jinja2 import pass_context


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


@pass_context
def gemini_parts(
    ctx: Any,
    files: Optional[List[Dict[str, Any]]],
    input_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build a Gemini parts array merging a text part with file inline_data parts.

    Usage: {{ files | gemini_parts | tojson }}
    """
    text = input_text if input_text is not None else ctx.get("input", "")
    parts: List[Dict[str, Any]] = [{"text": text}]
    parts.extend(to_gemini(files))
    return parts


@pass_context
def openai_content(
    ctx: Any,
    files: Optional[List[Dict[str, Any]]],
    input_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build an OpenAI content array merging a text block with image_url blocks.

    Usage: {{ files | openai_content | tojson }}
    """
    text = input_text if input_text is not None else ctx.get("input", "")
    content: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    content.extend(to_openai(files))
    return content


@pass_context
def anthropic_content(
    ctx: Any,
    files: Optional[List[Dict[str, Any]]],
    input_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build an Anthropic content array merging a text block with image/document blocks.

    Usage: {{ files | anthropic_content | tojson }}
    """
    text = input_text if input_text is not None else ctx.get("input", "")
    content: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    content.extend(to_anthropic(files))
    return content


def to_gemini_contents(
    messages: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Convert OpenAI-style messages to Gemini contents format.

    - role "assistant" → "model"
    - role "system" is dropped (pass system instructions via Gemini's
      ``systemInstruction`` field instead)
    - content string → parts: [{"text": content}]

    Usage: {{ messages | to_gemini_contents | tojson }}
    """
    ROLE_MAP = {"assistant": "model", "user": "user", "model": "model"}
    contents = []
    for msg in messages or []:
        role = msg.get("role", "user")
        if role == "system":
            continue
        content = msg.get("content", "")
        contents.append({"role": ROLE_MAP.get(role, role), "parts": [{"text": content}]})
    return contents


def to_anthropic_messages(
    messages: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Strip system messages from an OpenAI-style messages array for Anthropic.

    Anthropic's ``/messages`` API accepts the same ``{role, content}`` format
    as OpenAI but requires the system prompt to be passed separately as the
    top-level ``system`` field, not inside the messages array.

    Usage: {{ messages | to_anthropic_messages | tojson }}
    """
    return [msg for msg in (messages or []) if msg.get("role") != "system"]


FILE_FILTERS = {
    "to_anthropic": to_anthropic,
    "to_openai": to_openai,
    "to_gemini": to_gemini,
    "gemini_parts": gemini_parts,
    "openai_content": openai_content,
    "anthropic_content": anthropic_content,
    "to_gemini_contents": to_gemini_contents,
    "to_anthropic_messages": to_anthropic_messages,
}

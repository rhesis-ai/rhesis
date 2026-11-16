"""Estimate the input tokens a chat request will be billed for, before sending it.

For hosts that bound or price calls up front (see ``set_default_precall_check``).
Text is counted with LiteLLM's tokenizer. A file part is counted by what it holds:
a PDF by its pages, anything else by its size, so one large document can't pass
as a single small image.
"""

import base64
import binascii
import logging
import re
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Tokens counted for one image. Gemini bills up to 1,120 at high resolution.
IMAGE_PART_TOKENS = 2_000

#: Tokens counted per PDF page. Gemini bills 258 to 560 depending on resolution.
PDF_PAGE_TOKENS = 600

#: Tokens counted per byte of any other file, as if it were plain text.
BYTES_PER_TOKEN = 4

#: Above this many characters the tokenizer is skipped, since it is slow on long text.
#: Characters / 3 stands in, which is above the real count for English.
TOKENIZE_MAX_CHARS = 200_000
CHARS_PER_TOKEN_ESTIMATE = 3

_DATA_URI = re.compile(r"^data:([^;,]*)(;base64)?,", re.IGNORECASE)
_PDF_PAGE_MARKER = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")


def _pdf_pages(data: bytes) -> Optional[int]:
    try:
        from pdfminer.pdfpage import PDFPage

        return sum(1 for _ in PDFPage.get_pages(BytesIO(data)))
    except Exception:
        # Not installed, or a file pdfminer can't walk. Page objects stored in
        # compressed streams are missed here, so this is a fallback only.
        pages = len(_PDF_PAGE_MARKER.findall(data))
        return pages or None


def _file_tokens(url: str) -> int:
    """Tokens for one ``image_url``/``file`` part, from its data URI when it has one."""
    match = _DATA_URI.match(url)
    if not match:
        return IMAGE_PART_TOKENS
    mime = (match.group(1) or "").lower()
    payload = url[match.end() :]
    if mime.startswith("image/"):
        return IMAGE_PART_TOKENS
    try:
        data = base64.b64decode(payload) if match.group(2) else payload.encode()
    except (binascii.Error, ValueError):
        return max(IMAGE_PART_TOKENS, len(payload) // BYTES_PER_TOKEN)
    if mime == "application/pdf":
        pages = _pdf_pages(data)
        if pages is not None:
            return max(IMAGE_PART_TOKENS, pages * PDF_PAGE_TOKENS)
    return max(IMAGE_PART_TOKENS, len(data) // BYTES_PER_TOKEN)


def _part_url(part: Dict[str, Any]) -> str:
    for key in ("image_url", "file", "input_file"):
        value = part.get(key)
        if isinstance(value, dict):
            value = value.get("url") or value.get("file_data") or value.get("file_id")
        if isinstance(value, str):
            return value
    return ""


def _text_and_file_tokens(messages: Iterable[Dict[str, Any]]) -> Tuple[List[str], int]:
    texts: List[str] = []
    file_tokens = 0
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
            continue
        for part in content or []:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text") or ""))
            elif isinstance(part, dict):
                file_tokens += _file_tokens(_part_url(part))
            else:
                texts.append(str(part))
    return texts, file_tokens


def estimate_input_tokens(model_name: str, messages: List[Dict[str, Any]]) -> int:
    """Input tokens one chat transcript will be billed for, erring high."""
    import litellm

    texts, file_tokens = _text_and_file_tokens(messages)
    chars = sum(len(text) for text in texts)
    if chars > TOKENIZE_MAX_CHARS:
        return chars // CHARS_PER_TOKEN_ESTIMATE + file_tokens
    try:
        return litellm.token_counter(model=model_name, text="\n".join(texts)) + file_tokens
    except Exception:
        return chars // CHARS_PER_TOKEN_ESTIMATE + file_tokens

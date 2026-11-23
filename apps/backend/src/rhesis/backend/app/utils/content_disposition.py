"""``Content-Disposition`` values for downloads named by users."""

import os
from urllib.parse import quote


def attachment_disposition(filename: str, fallback: str = "download") -> str:
    """An ASCII ``filename`` for old clients plus the real name as UTF-8 (RFC 6266).

    The name may hold quotes, path separators or non-Latin-1 text, none of which can
    go into the header as-is. A name with nothing readable left before its extension
    ("отчёт.pdf") falls back, keeping the extension when *fallback* has none.
    """
    name = filename or fallback
    ascii_name = "".join(c if c.isascii() and (c.isalnum() or c in "-_. ") else "_" for c in name)
    stem, ext = os.path.splitext(ascii_name)
    if not any(c.isalnum() for c in stem):
        ascii_name = fallback if os.path.splitext(fallback)[1] else f"{fallback}{ext}"
    # safe="": a "/" in the name must not reach the file name.
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"

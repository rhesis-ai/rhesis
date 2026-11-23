"""``Content-Disposition`` values for downloads named by users."""

from urllib.parse import quote


def attachment_disposition(filename: str, fallback: str = "download") -> str:
    """An ASCII ``filename`` for old clients plus the real name as UTF-8 (RFC 6266).

    The name may hold quotes, path separators or non-Latin-1 text, none of which can
    go into the header as-is.
    """
    name = filename or fallback
    ascii_name = "".join(c if c.isascii() and (c.isalnum() or c in "-_. ") else "_" for c in name)
    if not ascii_name.strip("_ ."):
        ascii_name = fallback
    # safe="": a "/" in the name must not reach the file name.
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"

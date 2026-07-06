"""Shared helper for turning Target `files` attachments into LangChain content blocks.

Used by LangChainTarget and LangGraphTarget, both of which build messages out of
langchain_core message content. langchain_core is an optional dependency of
rhesis-penelope, so the import is deferred to call time - importing this module
(and anything that imports it) must not require langchain_core to be installed.
"""

from typing import Any, List, Optional, Union


def files_to_content_blocks(message: str, files: Optional[List[Any]]) -> Union[str, List[Any]]:
    """Build LangChain message content for `message`, attaching `files` as content
    blocks if present.

    `files` entries may be either a dict with inline base64 `data`, or a
    `FileReference` (object-storage-backed, see `_file_compat.py`).

    Returns the plain `message` string when there are no files, or a list of content
    blocks (text + media) suitable for a HumanMessage when there are.
    """
    if not files:
        return message

    from langchain_core.messages.content import create_text_block

    return [create_text_block(message), *(_file_to_block(f) for f in files)]


def _file_to_block(file: Any) -> Any:
    import base64

    from langchain_core.messages.content import (
        create_audio_block,
        create_file_block,
        create_image_block,
        create_text_block,
        create_video_block,
    )

    from rhesis.penelope._file_compat import file_attr, file_bytes_and_type, file_extracted_text

    extracted_text = file_extracted_text(file)
    if extracted_text:
        filename = file_attr(file, "filename", "attachment")
        return create_text_block(f"[Attached file: {filename}]\n{extracted_text}")

    data, content_type = file_bytes_and_type(file)
    kwargs = {"base64": base64.b64encode(data).decode(), "mime_type": content_type}
    if content_type.startswith("image/"):
        return create_image_block(**kwargs)
    if content_type.startswith("audio/"):
        return create_audio_block(**kwargs)
    if content_type.startswith("video/"):
        return create_video_block(**kwargs)
    return create_file_block(**kwargs)

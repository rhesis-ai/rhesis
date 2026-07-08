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


async def afiles_to_content_blocks(
    message: str, files: Optional[List[Any]]
) -> Union[str, List[Any]]:
    """Async sibling of :func:`files_to_content_blocks`.

    Uses ``FileReference.aread_bytes()`` to materialize object-storage
    attachments so building the blocks doesn't block the event loop; the
    attachments are fetched concurrently (order preserved).
    """
    if not files:
        return message

    import asyncio

    from langchain_core.messages.content import create_text_block

    blocks = await asyncio.gather(*(_afile_to_block(f) for f in files))
    return [create_text_block(message), *blocks]


def _extracted_text_block(file: Any, extracted_text: str) -> Any:
    from langchain_core.messages.content import create_text_block

    from rhesis.penelope._file_compat import file_attr

    filename = file_attr(file, "filename", "attachment")
    return create_text_block(f"[Attached file: {filename}]\n{extracted_text}")


def _block_from_bytes(data: bytes, content_type: str) -> Any:
    import base64

    from langchain_core.messages.content import (
        create_audio_block,
        create_file_block,
        create_image_block,
        create_video_block,
    )

    kwargs = {"base64": base64.b64encode(data).decode(), "mime_type": content_type}
    if content_type.startswith("image/"):
        return create_image_block(**kwargs)
    if content_type.startswith("audio/"):
        return create_audio_block(**kwargs)
    if content_type.startswith("video/"):
        return create_video_block(**kwargs)
    return create_file_block(**kwargs)


def _file_to_block(file: Any) -> Any:
    from rhesis.penelope._file_compat import file_bytes_and_type, file_extracted_text

    extracted_text = file_extracted_text(file)
    if extracted_text:
        return _extracted_text_block(file, extracted_text)

    data, content_type = file_bytes_and_type(file)
    return _block_from_bytes(data, content_type)


async def _afile_to_block(file: Any) -> Any:
    """Async sibling of :func:`_file_to_block` - uses ``aread_bytes()``."""
    from rhesis.penelope._file_compat import afile_bytes_and_type, file_extracted_text

    extracted_text = file_extracted_text(file)
    if extracted_text:
        return _extracted_text_block(file, extracted_text)

    data, content_type = await afile_bytes_and_type(file)
    return _block_from_bytes(data, content_type)

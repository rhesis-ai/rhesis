"""Shared helper for turning Target `files` attachments into LangChain content blocks.

Used by LangChainTarget and LangGraphTarget, both of which build messages out of
langchain_core message content.
"""

from typing import Any, Dict, List, Optional, Union

from langchain_core.messages.content import (
    create_audio_block,
    create_file_block,
    create_image_block,
    create_text_block,
    create_video_block,
)


def files_to_content_blocks(
    message: str, files: Optional[List[Dict[str, Any]]]
) -> Union[str, List[Any]]:
    """Build LangChain message content for `message`, attaching `files` as content
    blocks if present.

    Returns the plain `message` string when there are no files, or a list of content
    blocks (text + media) suitable for a HumanMessage when there are.
    """
    if not files:
        return message
    return [create_text_block(message), *(_file_to_block(f) for f in files)]


def _file_to_block(file: Dict[str, Any]) -> Any:
    content_type = file.get("content_type") or ""
    kwargs = {"base64": file["data"], "mime_type": content_type}
    if content_type.startswith("image/"):
        return create_image_block(**kwargs)
    if content_type.startswith("audio/"):
        return create_audio_block(**kwargs)
    if content_type.startswith("video/"):
        return create_video_block(**kwargs)
    return create_file_block(**kwargs)

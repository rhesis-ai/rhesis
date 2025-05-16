"""Utility functions for the Rhesis SDK."""

from typing import Optional

import tiktoken


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> Optional[int]:
    """Count the number of tokens in a given text string using tiktoken.

    Args:
        text: The input text to count tokens for
        encoding_name: The name of the encoding to use. Defaults to cl100k_base
                      (used by GPT-4 and GPT-3.5-turbo)

    Returns:
        Optional[int]: The number of tokens in the text, or None if encoding fails

    Examples:
        >>> count_tokens("Hello, world!")
        4
        >>> count_tokens("Complex text", encoding_name="p50k_base")
        2
    """
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception as e:
        # Log the error but don't raise it to avoid breaking client code
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to count tokens: {str(e)}")
        return None

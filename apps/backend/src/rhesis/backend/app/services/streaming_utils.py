"""Shared utilities for NDJSON streaming responses."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from rhesis.sdk.synthesizers.streaming import IncrementalJsonArrayParser

logger = logging.getLogger(__name__)

__all__ = ["ndjson", "IncrementalJsonArrayParser", "IncrementalConfigParser"]

_CONFIG_ARRAY_KEYS = ("behaviors", "topics", "categories")


def ndjson(event: Dict[str, Any]) -> bytes:
    """Encode a single NDJSON event."""
    return (json.dumps(event) + "\n").encode("utf-8")


class IncrementalConfigParser:
    """Parse a streaming config response with multiple named arrays.

    Wraps ``IncrementalJsonArrayParser`` and tracks which top-level key
    (``behaviors``, ``topics``, ``categories``) each object belongs to by
    detecting when the inner parser enters each successive array.

    Yields ``(category, obj)`` tuples.
    """

    def __init__(self):
        self._inner = IncrementalJsonArrayParser()
        self._current_key: Optional[str] = None
        self._next_array_index = 0

    def feed(self, chunk: str) -> List[Tuple[str, dict]]:
        results: List[Tuple[str, dict]] = []
        for char in chunk:
            was_in_array = self._inner._in_array
            objects = self._inner.feed(char)
            if not was_in_array and self._inner._in_array:
                if self._next_array_index < len(_CONFIG_ARRAY_KEYS):
                    self._current_key = _CONFIG_ARRAY_KEYS[self._next_array_index]
                    self._next_array_index += 1
                else:
                    self._current_key = "unknown"
            category = self._current_key or "unknown"
            results.extend((category, obj) for obj in objects)
        return results

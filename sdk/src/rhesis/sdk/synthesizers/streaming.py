"""Incremental JSON parsing utilities for streaming LLM responses."""

import json
import logging
from typing import List

logger = logging.getLogger(__name__)


class IncrementalJsonArrayParser:
    """Extract complete JSON objects from a streaming JSON response.

    Designed for structured output shaped like ``{"key": [{...}, ...]}``.
    Feeds token chunks incrementally and yields each complete object in the
    top-level array as soon as its closing brace is detected.  Correctly
    handles escaped characters and strings containing braces.
    """

    def __init__(self):
        self._buffer: str = ""
        self._pos: int = 0
        self._in_array: bool = False
        self._brace_depth: int = 0
        self._in_string: bool = False
        self._escape_next: bool = False
        self._obj_start: int = -1

    def feed(self, chunk: str) -> List[dict]:
        """Append *chunk* to the internal buffer and return any newly complete objects."""
        self._buffer += chunk
        results: List[dict] = []

        while self._pos < len(self._buffer):
            c = self._buffer[self._pos]

            if self._escape_next:
                self._escape_next = False
                self._pos += 1
                continue

            if c == "\\" and self._in_string:
                self._escape_next = True
                self._pos += 1
                continue

            if c == '"':
                self._in_string = not self._in_string
                self._pos += 1
                continue

            if self._in_string:
                self._pos += 1
                continue

            if not self._in_array:
                if c == "[":
                    self._in_array = True
            else:
                if c == "{":
                    if self._brace_depth == 0:
                        self._obj_start = self._pos
                    self._brace_depth += 1
                elif c == "}":
                    self._brace_depth -= 1
                    if self._brace_depth == 0 and self._obj_start >= 0:
                        obj_str = self._buffer[self._obj_start : self._pos + 1]
                        try:
                            results.append(json.loads(obj_str))
                        except json.JSONDecodeError:
                            logger.warning(
                                "Failed to parse streamed JSON object: %.120s",
                                obj_str,
                            )
                        self._obj_start = -1
                elif c == "]":
                    self._in_array = False

            self._pos += 1

        return results

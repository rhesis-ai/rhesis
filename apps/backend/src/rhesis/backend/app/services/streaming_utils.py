"""Shared utilities for NDJSON streaming responses."""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from rhesis.sdk.synthesizers.streaming import IncrementalJsonArrayParser

logger = logging.getLogger(__name__)

__all__ = ["ndjson", "IncrementalJsonArrayParser", "IncrementalConfigParser"]


def ndjson(event: Dict[str, Any]) -> bytes:
    """Encode a single NDJSON event."""
    return (json.dumps(event) + "\n").encode("utf-8")


_KEY_PATTERN = re.compile(r'"(behaviors|topics|categories)"\s*:')


class IncrementalConfigParser:
    """Parse a streaming config response with multiple named arrays.

    Wraps ``IncrementalJsonArrayParser`` and tracks which top-level key
    (``behaviors``, ``topics``, ``categories``) each object belongs to by
    scanning for key names before ``[`` in the token stream.

    Yields ``(category, obj)`` tuples.
    """

    def __init__(self):
        self._inner = IncrementalJsonArrayParser()
        self._raw_buffer: str = ""
        self._current_key: Optional[str] = None
        self._scan_pos: int = 0

    def feed(self, chunk: str) -> List[Tuple[str, dict]]:
        self._raw_buffer += chunk

        # Scan for key names to track which array we're in
        while self._scan_pos < len(self._raw_buffer):
            remaining = self._raw_buffer[self._scan_pos :]
            m = _KEY_PATTERN.search(remaining)
            if m:
                self._current_key = m.group(1)
                self._scan_pos += m.end()
            else:
                # No more matches in current buffer -- advance to near the end
                # but leave enough room for a partial match at the boundary.
                self._scan_pos = max(0, len(self._raw_buffer) - 30)
                break

        objects = self._inner.feed(chunk)
        category = self._current_key or "unknown"
        return [(category, obj) for obj in objects]

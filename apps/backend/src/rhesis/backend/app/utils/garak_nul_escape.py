"""
Reversible NUL escaping for Garak prompts and notes.

Some Garak probes (``glitch.Glitch``, ``glitch.GlitchFull``) use the NUL character
as the glitch token, in both the prompt and the detector trigger. PostgreSQL can
store NUL in neither a ``text`` column nor JSONB, and stripping it would change
what the probe sends and what the detector looks for.

So the importer escapes such a test's prompt and notes before storing them and
sets ``NUL_ESCAPED_KEY`` in its ``test_metadata``; execution decodes them again
only when that flag is set. Rows without the flag are left exactly as stored.
"""

import re
from typing import Any, Dict, Optional, Tuple

NUL_ESCAPED_KEY = "garak_nul_escaped"

_ESCAPE_SEQUENCE = re.compile(r"\\(\\|0)")


def _escape(value: str) -> str:
    # Backslashes are escaped too, so a literal "\0" in the source survives decoding.
    return value.replace("\\", "\\\\").replace("\x00", "\\0")


def _unescape(value: str) -> str:
    return _ESCAPE_SEQUENCE.sub(lambda m: "\x00" if m.group(1) == "0" else "\\", value)


def _contains_nul(value: Any) -> bool:
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, dict):
        return any(_contains_nul(k) or _contains_nul(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_nul(v) for v in value)
    return False


def _map_strings(value: Any, fn) -> Any:
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, dict):
        return {_map_strings(k, fn): _map_strings(v, fn) for k, v in value.items()}
    if isinstance(value, list):
        return [_map_strings(v, fn) for v in value]
    return value


def encode_prompt_and_notes(
    prompt: str, notes: Optional[Dict[str, Any]], test_metadata: Dict[str, Any]
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Escape prompt and notes if either contains NUL, flagging it in ``test_metadata``.

    Both are escaped together because the single flag says how to read both.
    """
    if not (_contains_nul(prompt) or _contains_nul(notes)):
        return prompt, notes
    test_metadata[NUL_ESCAPED_KEY] = True
    return _escape(prompt), _map_strings(notes, _escape)


def is_nul_escaped(test_metadata: Optional[Dict[str, Any]]) -> bool:
    return bool((test_metadata or {}).get(NUL_ESCAPED_KEY))


def decode_prompt(prompt: str, test_metadata: Optional[Dict[str, Any]]) -> str:
    """Return the prompt as the probe produced it."""
    if not prompt or not is_nul_escaped(test_metadata):
        return prompt
    return _unescape(prompt)


def decode_notes(test_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return ``garak_notes`` as the probe produced them."""
    notes = (test_metadata or {}).get("garak_notes")
    if not notes or not is_nul_escaped(test_metadata):
        return notes
    return _map_strings(notes, _unescape)

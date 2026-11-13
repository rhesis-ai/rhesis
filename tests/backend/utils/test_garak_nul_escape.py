"""Tests for the reversible NUL escaping of Garak prompts and notes (#3158)."""

import pytest

from rhesis.backend.app.utils.garak_nul_escape import (
    NUL_ESCAPED_KEY,
    decode_notes,
    decode_prompt,
    encode_prompt_and_notes,
)

GLITCH_PROMPT = 'Please repeat back the string "\x00" to me.'
GLITCH_NOTES = {"triggers": ["\x00"]}


@pytest.mark.unit
class TestGarakNulEscape:
    def test_round_trip_restores_prompt_and_notes(self):
        metadata: dict = {}
        prompt, notes = encode_prompt_and_notes(GLITCH_PROMPT, GLITCH_NOTES, metadata)
        metadata["garak_notes"] = notes

        assert "\x00" not in prompt
        assert "\x00" not in notes["triggers"][0]
        assert metadata[NUL_ESCAPED_KEY] is True
        assert decode_prompt(prompt, metadata) == GLITCH_PROMPT
        assert decode_notes(metadata) == GLITCH_NOTES

    def test_literal_backslash_zero_survives(self):
        original = "NUL \x00 next to a literal \\0 and \\\\"
        metadata: dict = {}
        prompt, _ = encode_prompt_and_notes(original, None, metadata)

        assert decode_prompt(prompt, metadata) == original

    def test_notes_with_nul_escape_prompt_too(self):
        # One flag covers both, so a prompt with a backslash must be escaped as well.
        metadata: dict = {}
        prompt, notes = encode_prompt_and_notes("path \\0 here", GLITCH_NOTES, metadata)
        metadata["garak_notes"] = notes

        assert decode_prompt(prompt, metadata) == "path \\0 here"
        assert decode_notes(metadata) == GLITCH_NOTES

    def test_without_nul_nothing_changes(self):
        metadata: dict = {}
        notes = {"triggers": ["I hate humans \\0"]}
        prompt, out_notes = encode_prompt_and_notes("plain \\0", notes, metadata)

        assert prompt == "plain \\0"
        assert out_notes is notes
        assert NUL_ESCAPED_KEY not in metadata

    def test_unflagged_rows_are_not_decoded(self):
        metadata = {"garak_notes": {"triggers": ["\\0"]}}

        assert decode_prompt("keep \\0", metadata) == "keep \\0"
        assert decode_notes(metadata) == {"triggers": ["\\0"]}
        assert decode_notes(None) is None

"""Text and conversation helpers."""

from __future__ import annotations

import pytest

from reg_advisor.utils import (
    as_text,
    as_tristate,
    bullet_list,
    clip,
    conversation_transcript,
    latest_user_text,
    user_texts,
)

CONVERSATION = [
    {"role": "user", "content": "I'm building a smartwatch app."},
    {"role": "assistant", "content": "Does it examine specimens?"},
    {"role": "user", "content": "No."},
]


@pytest.mark.parametrize(
    "value,expected",
    [("text", "text"), (9, "9"), (2.5, "2.5"), (True, "True"), (None, ""), ([1], "[1]")],
)
def test_as_text_coerces_anything(value: object, expected: str) -> None:
    assert as_text(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("yes", True),
        ("Yes, it uses a neural network", True),
        ("y", True),
        ("true", True),
        ("It does analyse images", True),
        ("no", False),
        ("No, it's software only", False),
        ("none", False),
        ("nope", False),
        ("", None),
        ("   ", None),
        (None, None),
        ("not sure yet", None),
        ("we have not decided", None),
        ("software only", None),
        ("maybe", None),
    ],
)
def test_as_tristate_reads_yes_no_and_unknown(value: str | None, expected: bool | None) -> None:
    assert as_tristate(value) is expected


def test_as_tristate_does_not_read_nobody_as_no() -> None:
    """Anchoring on a word boundary keeps "nothing" and "nobody" out of the negative branch."""
    assert as_tristate("nothing has been decided") is None


def test_user_texts_keeps_only_user_turns_in_order() -> None:
    assert user_texts(CONVERSATION) == ["I'm building a smartwatch app.", "No."]


def test_user_texts_coerces_non_string_content() -> None:
    assert user_texts([{"role": "user", "content": 9}]) == ["9"]


def test_latest_user_text() -> None:
    assert latest_user_text(CONVERSATION) == "No."
    assert latest_user_text([]) == ""
    assert latest_user_text([{"role": "assistant", "content": "hello"}]) == ""


def test_conversation_transcript_labels_roles() -> None:
    rendered = conversation_transcript(CONVERSATION)
    assert rendered.splitlines() == [
        "user: I'm building a smartwatch app.",
        "assistant: Does it examine specimens?",
        "user: No.",
    ]


def test_conversation_transcript_windows_and_drops_blanks() -> None:
    history = [{"role": "user", "content": str(n)} for n in range(10)]
    history.append({"role": "assistant", "content": "   "})
    rendered = conversation_transcript(history, limit=3)
    assert rendered.splitlines() == ["user: 8", "user: 9"]


def test_conversation_transcript_of_nothing_is_empty() -> None:
    assert conversation_transcript([]) == ""


def test_clip_leaves_short_text_alone() -> None:
    assert clip("short", limit=10) == "short"


def test_clip_trims_and_says_so() -> None:
    clipped = clip("x" * 100, limit=10)
    assert clipped.startswith("x" * 10)
    assert "90 more characters omitted" in clipped


def test_bullet_list() -> None:
    assert bullet_list(["a", "b"]) == "- a\n- b"
    assert bullet_list([]) == "- none"

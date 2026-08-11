"""Text and conversation helpers shared by the coordinator tools and the turn layer."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from functools import lru_cache

# Anchored at the start of the answer, so "no, it's software only" reads as a no while
# "not sure yet" and "nobody has decided" fall through to unknown.
_AFFIRMATIVE = re.compile(
    r"^\s*(yes|yep|yeah|y|true|correct|affirmative|it does|we do|indeed|1)\b",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"^\s*(no|nope|nah|n|false|none|never|it does not|it doesn't|we do not|we don't|0)\b",
    re.IGNORECASE,
)


def as_text(value: object) -> str:
    """Coerce a turn message or tool argument to text.

    A turn's message is not always a ``str`` by the time it reaches us. An HTTP client can send
    a bare JSON number, and a model can answer a ``"type": "string"`` tool parameter with a
    number or a boolean. Everything downstream — the scope-flag regexes, the profile slots, the
    classifier's keyword checks — assumes text.
    """
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def as_tristate(value: str | None) -> bool | None:
    """Read a free-text answer as yes, no, or unknown.

    Unknown is a real answer here: the classifier reports the field as unresolved rather than
    picking a branch, which is what stops a shrug from becoming a determination.
    """
    text = as_text(value).strip()
    if not text:
        return None
    if _AFFIRMATIVE.match(text):
        return True
    if _NEGATIVE.match(text):
        return False
    return None


def _bounded(needle: str) -> str:
    """Word-boundary pattern for one needle. A trailing "*" becomes a stem match."""
    stem = needle.endswith("*")
    core = re.escape(needle[:-1] if stem else needle)
    prefix = r"\b" if needle[:1].isalnum() else ""
    suffix = r"\w*" if stem else (r"\b" if needle[-1:].isalnum() else "")
    return prefix + core + suffix


@lru_cache(maxsize=None)
def _matcher(needles: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join(_bounded(needle) for needle in needles))


def matches_any(haystack: str, needles: tuple[str, ...]) -> bool:
    """True when any needle appears in ``haystack`` as a whole word or a stem.

    Word boundaries are load-bearing rather than tidy: plain substring matching reads "applied
    to intact skin" as software, because "app" is in there.
    """
    return bool(_matcher(needles).search(haystack.lower()))


def as_slot_text(value: object) -> str | None:
    """Normalise a value to a profile slot, or ``None`` to drop it.

    A model answering a ``"type": "string"`` parameter with a bare JSON number or boolean is
    common enough that dropping non-strings would lose real answers. Anything that is not a
    scalar is dropped rather than stringified — a dict rendered as ``"{'eu': True}"`` is a slot
    value nothing downstream can read.
    """
    if isinstance(value, (str, int, float, bool)):
        return as_text(value).strip() or None
    return None


def user_texts(history: Iterable[dict[str, str]]) -> list[str]:
    """Every user turn from a replayed conversation, oldest first.

    The scope rules take this rather than the whole history: scanning the assistant's own
    referral copy would re-trigger the check on every later turn.
    """
    return [as_text(item.get("content")) for item in history if item.get("role") == "user"]


def latest_user_text(history: Iterable[dict[str, str]]) -> str:
    """The most recent user turn, or ``""`` when there is none."""
    texts = user_texts(history)
    return texts[-1] if texts else ""


def conversation_transcript(
    history: Sequence[dict[str, str]],
    *,
    limit: int = 12,
) -> str:
    """Render the recent conversation as text, for forwarding to a specialist agent.

    ADK hands a sub-agent one request string, so a short answer like "software only" only makes
    sense alongside the question that prompted it.
    """
    lines = [
        f"{item.get('role', 'user')}: {as_text(item.get('content')).strip()}"
        for item in history[-limit:]
        if as_text(item.get("content")).strip()
    ]
    return "\n".join(lines)


def clip(text: str, limit: int = 4000) -> str:
    """Trim an over-long paste so one turn cannot swamp a prompt."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n[... {len(text) - limit} more characters omitted ...]"


def bullet_list(items: Iterable[str]) -> str:
    """Render items as a dash list, or a dash-none line when empty."""
    rendered = [f"- {item}" for item in items]
    return "\n".join(rendered) if rendered else "- none"


__all__ = [
    "as_slot_text",
    "as_text",
    "as_tristate",
    "bullet_list",
    "clip",
    "conversation_transcript",
    "latest_user_text",
    "matches_any",
    "user_texts",
]

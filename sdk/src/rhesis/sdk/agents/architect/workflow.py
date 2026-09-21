"""Workflow path routing for lazy phase prompt loading.

Classification is generic; the intents it classifies into are data. See
``skills/rhesis/references/intents.yaml`` and :mod:`rhesis.sdk.agents.architect.intents`.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from rhesis.sdk.agents.architect.intents import (
    Intent,
    WorkflowPath,
    load_intents,
    menu_intents,
)

# WorkflowPath lives with the intent data it constrains; re-exported here because
# this is where the rest of the agent has always imported it from.
__all__ = ["WorkflowPath", "infer_intent", "infer_workflow_path", "resolve_workflow_path_update"]


@lru_cache(maxsize=None)
def _menu_pattern(intent: Intent) -> Optional[re.Pattern[str]]:
    """Match the menu choice written out, e.g. "3 - build from my PRD"."""
    menu = intent.menu
    if menu is None:
        return None

    alternatives = []
    if menu.cues:
        # Only `phrases` are documented as regexes; cues and the word are literals.
        choice = f"{menu.number}|{re.escape(menu.word)}"
        cues = "|".join(re.escape(cue) for cue in menu.cues)
        alternatives.append(rf"(?:^|\b)(?:{choice})\b.*(?:{cues})")
    alternatives.extend(menu.phrases)
    if not alternatives:
        return None
    return re.compile("|".join(alternatives))


def infer_intent(message: str, *, has_attachments: bool = False) -> Optional[Intent]:
    """Detect the user's intent from their message. Returns None if ambiguous."""
    text = message.lower().strip()

    for intent in menu_intents():
        if text in {str(intent.menu.number), intent.menu.word}:
            return intent

    for intent in menu_intents():
        pattern = _menu_pattern(intent)
        if pattern is not None and pattern.search(text):
            return intent

    # A long message with an attachment is a pasted document, whatever it says.
    if has_attachments:
        for intent in load_intents():
            minimum = intent.attachment_min_length
            if minimum is not None and len(message) > minimum:
                return intent

    for intent in load_intents():
        if len(message) <= intent.keyword_min_length:
            continue
        if any(signal in text for signal in intent.keyword_signals):
            return intent

    return None


def infer_workflow_path(message: str, *, has_attachments: bool = False) -> WorkflowPath | None:
    """Detect workflow path from the user message. Returns None if ambiguous."""
    intent = infer_intent(message, has_attachments=has_attachments)
    return None if intent is None else intent.workflow_path


def resolve_workflow_path_update(
    current: WorkflowPath,
    message: str,
    *,
    has_attachments: bool = False,
) -> WorkflowPath | None:
    """Return an updated path when user signals warrant re-classification."""
    inferred = infer_workflow_path(message, has_attachments=has_attachments)
    if inferred is None:
        return None
    if current == WorkflowPath.UNSET:
        return inferred
    # Exploration is the default guess, so any other signal may still override it.
    if current == WorkflowPath.EXPLORE and inferred != WorkflowPath.EXPLORE:
        return inferred
    return None
